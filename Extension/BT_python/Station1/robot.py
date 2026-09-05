import numpy as np
import omni.usd
import omni.kit.commands
from pxr import UsdGeom, Gf
from isaacsim.robot_motion.cumotion import (
    load_cumotion_robot,
    CumotionWorldInterface,
    GraphBasedMotionPlanner
)
from isaacsim.core.prims import SingleArticulation
from isaacsim.core.utils.types import ArticulationAction

class RobotController:
    def __init__(self, prim_path: str, name: str, side: str, base_translation: list, drop_location: list, x_offset: float = 0.07, y_offset: float = 0.0, z_offset: float = 0.18, approach_height: float = 0.5):
        self.prim_path = prim_path
        self.name = name
        self.side = side.lower()
        self.base_translation = base_translation  
        self.drop_location = drop_location
        
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.z_offset = z_offset
        
        self.approach_height = approach_height 
        
        self.is_idle = True
        self.state = "IDLE"
        self.current_screw_path = None
        self.current_screw_coord = None
        self.wait_timer = 0.0
        self.last_completed_screw = None
        
        self.cumotion_robot = load_cumotion_robot(
            directory=r"D:\Battery_Disassembling\FanucArm",
            urdf_filename="Fanuc.urdf",
            xrdf_filename="Fanuc.xrdf"
        )
        self.world = CumotionWorldInterface()
        self.planner = GraphBasedMotionPlanner(
            cumotion_robot=self.cumotion_robot,
            cumotion_world_interface=self.world,
            tool_frame="J6_link"
        )
        
        self.robot = None
        self.current_trajectory = None
        self.t = 0.0
        self.DOWN_QUAT = np.array([0.0, -0.70710678, 0.0, 0.70710678])
        
    def initialize(self):
        if self.robot is None:
            self.robot = SingleArticulation(self.prim_path, name=self.name)
        self.robot.initialize()
        
    def _convert_coordinates(self, world_coords):
        world_x, world_y, world_z = world_coords
        trans_x, trans_y, trans_z = self.base_translation
        
        if self.side == "left":
            robot_x = trans_y - world_y
            robot_y = world_x - trans_x
        elif self.side == "right":
            robot_x = world_y - trans_y
            robot_y = trans_x - world_x
        else:
            robot_x, robot_y = world_x, world_y
            
        robot_z = world_z - trans_z 
        
        return np.array([robot_x, robot_y, robot_z])
        
    def _plan_and_move(self, global_target):
        local_target = self._convert_coordinates(global_target)
        q0 = self.robot.get_joint_positions()
        traj = self.planner.plan_to_pose_target(q0, local_target, self.DOWN_QUAT)
        
        if traj is None:
            print(f"[{self.name}] Planning failed for target: {local_target}.")
            self.state = "FAIL_WAIT"
            self.wait_timer = 0.5 
            return
            
        self.current_trajectory = traj.to_minimal_time_joint_trajectory(
            max_velocities=[3.66, 3.66, 4.62, 7.33, 7.85, 12.56],
            max_accelerations=[10, 10, 10, 10, 10, 10],
            robot_joint_space=["J1", "J2", "J3", "J4", "J5", "J6"],
            active_joints=["J1", "J2", "J3", "J4", "J5", "J6"]
        )
        self.t = 0.0
        
    def assign_task(self, screw_data):
        self.is_idle = False
        self.current_screw_path, self.current_screw_coord = screw_data
        
        self.state = "APPROACH"
        approach_coord = [
            self.current_screw_coord[0] + self.x_offset, 
            self.current_screw_coord[1] + self.y_offset, 
            self.current_screw_coord[2] + self.z_offset + self.approach_height
        ]
        
        print(f"[{self.name}] Approaching screw at {approach_coord}")
        self._plan_and_move(approach_coord)
        
    def update_step(self, dt, e_stop=False):
        if self.is_idle or self.robot is None:
            return
            
        if self.state == "FAIL_WAIT":
            if not e_stop: self.wait_timer -= dt
            if self.wait_timer <= 0:
                self.is_idle = True
                self.state = "IDLE"
            return
            
        if self.state == "WAIT":
            if not e_stop: self.wait_timer -= dt
            if self.wait_timer <= 0:
                stage = omni.usd.get_context().get_stage()
                prim = stage.GetPrimAtPath(self.current_screw_path)
                if prim.IsValid():
                    omni.kit.commands.execute('TransformPrimSRT',
                        path=self.current_screw_path,
                        new_scale=Gf.Vec3d(0.001, 0.001, 0.001)
                    )
                    print(f"[{self.name}] Screw removed: {self.current_screw_path}")
                
                self.state = "RETRACT"
                retract_coord = [
                    self.current_screw_coord[0] + self.x_offset, 
                    self.current_screw_coord[1] + self.y_offset, 
                    self.current_screw_coord[2] + self.z_offset + self.approach_height
                ]
                self._plan_and_move(retract_coord)
            return
            
        if self.state == "WAIT_DROP":
            if not e_stop: self.wait_timer -= dt
            if self.wait_timer <= 0:
                self.state = "IDLE"
                self.is_idle = True
                self.last_completed_screw = self.current_screw_path
                print(f"[{self.name}] Task Complete. Ready for next screw.")
            return

        if self.current_trajectory is None:
            return

        if self.t <= self.current_trajectory.duration:
            state = self.current_trajectory.get_target_state(self.t)
            self.robot.apply_action(ArticulationAction(joint_positions=state.joints.positions))
            if not e_stop:
                self.t += dt
        else:
            if not e_stop:
                if self.state == "APPROACH":
                    self.state = "ENGAGE"
                    engage_coord = [
                        self.current_screw_coord[0] + self.x_offset,
                        self.current_screw_coord[1] + self.y_offset,
                        self.current_screw_coord[2] + self.z_offset
                    ]
                    self._plan_and_move(engage_coord)
                    
                elif self.state == "ENGAGE":
                    self.state = "WAIT"
                    self.wait_timer = 1.0 
                    
                elif self.state == "RETRACT":
                    self.state = "DROP"
                    dynamic_drop = [
                        self.drop_location[0],
                        self.drop_location[1],
                        self.current_screw_coord[2] + self.z_offset + self.approach_height
                    ]
                    self._plan_and_move(dynamic_drop)
                    
                elif self.state == "DROP":
                    self.state = "WAIT_DROP"
                    self.wait_timer = 0.5 
                    self.current_trajectory = None