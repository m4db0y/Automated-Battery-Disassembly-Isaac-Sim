import numpy as np
import omni.usd
import omni.kit.commands
from isaacsim.robot_motion.cumotion import (
    load_cumotion_robot,
    CumotionWorldInterface,
    GraphBasedMotionPlanner
)
from isaacsim.core.prims import SingleArticulation
from isaacsim.core.utils.types import ArticulationAction
from pxr import Usd, UsdGeom, Gf

class RobotController:
    def __init__(self, prim_path: str, name: str, base_translation: list, drop_location: list, x_offset: float = 0.05, y_offset: float = 0.0, z_offset: float = 0.17, approach_height: float = 0.75):
        self.prim_path = prim_path
        self.name = name
        self.base_translation = base_translation  
        self.drop_location = drop_location
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.z_offset = z_offset
        self.approach_height = approach_height 
        
        self.is_idle = True
        self.state = "IDLE"
        self.current_cell_path = None
        self.current_cell_coord = None
        self.wait_timer = 0.0
        self.last_completed_cell = None
        
        self.cumotion_robot = load_cumotion_robot(
            directory=r"D:\BatteryDT\Kuka",
            urdf_filename="Kuka.urdf",
            xrdf_filename="Kuka.xrdf"
        )
        self.world = CumotionWorldInterface()
        self.planner = GraphBasedMotionPlanner(
            cumotion_robot=self.cumotion_robot,
            cumotion_world_interface=self.world,
            tool_frame="tool0" 
        )
        
        self.robot = None
        self.current_trajectory = None
        self.t = 0.0
        
        self.JOINT_NAMES = ["joint_a1", "joint_a2", "joint_a3", "joint_a4", "joint_a5", "joint_a6"]
        self.MAX_VELOCITIES = [2.14675498, 2.00712877, 1.95476876, 3.12413963, 3.00196658, 3.82227106]
        self.MAX_ACCELERATIONS = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
        self.DOWN_QUAT = np.array([0.5, -0.5, 0.5, 0.5])
        self.dummy_cell_path = "/World/Kuka/tool0/Cell"
        self.spawned_cells_history = []
        
    def initialize(self):
        if self.robot is None:
            self.robot = SingleArticulation(self.prim_path, name=self.name)
        self.robot.initialize()
        
    def _convert_coordinates(self, world_coords):
        world_x, world_y, world_z = world_coords
        trans_x, trans_y, trans_z = self.base_translation
        robot_x = world_y - trans_y
        robot_y = trans_x - world_x
        robot_z = world_z - trans_z 
        return np.array([robot_x, robot_y, robot_z])

    def _spawn_dropped_cell(self):
        stage = omni.usd.get_context().get_stage()
        import time
        
        unique_id = int(time.time() * 1000)
        usd_file = r"D:\Battery_Disassembling\Battery\DCell.usd"
        spawn_path = f"/World/C1/Dropped_Cell_{unique_id}"

        # Define an empty Xform and link your local USD file to it
        spawned_prim = stage.DefinePrim(spawn_path, "Xform")
        spawned_prim.GetReferences().AddReference(usd_file)

        self.spawned_cells_history.append(spawn_path)
        if len(self.spawned_cells_history) > 5:
            oldest_path = self.spawned_cells_history.pop(0)
            stage.RemovePrim(oldest_path)
        
    def _plan_and_move(self, global_target):
        local_target = self._convert_coordinates(global_target)
        raw_joints = self.robot.get_joint_positions()
        if raw_joints is None: return False

        q0 = np.asarray(raw_joints, dtype=np.float64).copy()
        traj = self.planner.plan_to_pose_target(q0, local_target, self.DOWN_QUAT)
        
        if traj is None:
            self.state = "FAIL_WAIT"
            self.wait_timer = 0.5 
            return False
            
        self.current_trajectory = traj.to_minimal_time_joint_trajectory(
            max_velocities=self.MAX_VELOCITIES, max_accelerations=self.MAX_ACCELERATIONS,
            robot_joint_space=self.JOINT_NAMES, active_joints=self.JOINT_NAMES
        )
        self.t = 0.0
        return True
        
    def assign_task(self, cell_data):
        self.is_idle = False
        self.current_cell_path, self.current_cell_coord = cell_data
        self.state = "APPROACH"
        approach_coord = [
            self.current_cell_coord[0] + self.x_offset, 
            self.current_cell_coord[1] + self.y_offset, 
            self.current_cell_coord[2] + self.z_offset + self.approach_height
        ]
        success = self._plan_and_move(approach_coord)
        if not success:
            self.state = "IDLE"
            self.is_idle = True
        
    def update_step(self, dt, e_stop=False):
        if self.is_idle or self.robot is None: return
            
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

                # 1. RECURSIVELY HIDE EVERY NESTED MESH INSIDE THE PHYSICAL CELL
                cell_prim = stage.GetPrimAtPath(self.current_cell_path)
                if cell_prim.IsValid():
                    omni.kit.commands.execute('TransformPrimSRT',
                        path=self.current_cell_path,
                        new_scale=Gf.Vec3d(0.001, 0.001, 0.001)
                    )
                
                # 2. SHOW ROBOT DUMMY CELL ON GRAB
                dummy_prim = stage.GetPrimAtPath(self.dummy_cell_path)
                if dummy_prim.IsValid():
                    omni.kit.commands.execute('TransformPrimSRT',
                        path=self.dummy_cell_path,
                        new_scale=Gf.Vec3d(1.0, 1.0, 1.0)
                    )
                
                self.state = "RETRACT"
                retract_coord = [
                    self.current_cell_coord[0] + self.x_offset, 
                    self.current_cell_coord[1] + self.y_offset, 
                    self.current_cell_coord[2] + self.z_offset + self.approach_height
                ]
                self._plan_and_move(retract_coord)
            return
            
        if self.state == "WAIT_DROP":
            if not e_stop: self.wait_timer -= dt
            if self.wait_timer <= 0:
                stage = omni.usd.get_context().get_stage()
                
                # 3. HIDE ROBOT DUMMY CELL ON DROP
                dummy_prim = stage.GetPrimAtPath(self.dummy_cell_path)
                if dummy_prim.IsValid():
                    omni.kit.commands.execute('TransformPrimSRT',
                        path=self.dummy_cell_path,
                        new_scale=Gf.Vec3d(0.001, 0.001, 0.001)
                    )
                    
                self._spawn_dropped_cell()
                    
                # 4. RETRACT UPWARDS AFTER DROP
                self.state = "DROP_RETRACT"
                drop_retract_coord = [
                    self.drop_location[0],
                    self.drop_location[1],
                    self.current_cell_coord[2] + self.z_offset + self.approach_height
                ]
                self._plan_and_move(drop_retract_coord)
            return

        if self.current_trajectory is not None and self.t <= self.current_trajectory.duration:
            state = self.current_trajectory.get_target_state(self.t)
            if state is not None:
                self.robot.apply_action(ArticulationAction(joint_positions=state.joints.positions))
            if not e_stop: self.t += dt
            return

        if not e_stop:
            if self.state == "APPROACH":
                self.state = "ENGAGE"
                engage_coord = [
                    self.current_cell_coord[0] + self.x_offset,
                    self.current_cell_coord[1] + self.y_offset,
                    self.current_cell_coord[2] + self.z_offset
                ]
                self._plan_and_move(engage_coord)
                
            elif self.state == "ENGAGE":
                self.state = "WAIT"
                self.wait_timer = 0.3
                self.current_trajectory = None
                
            elif self.state == "RETRACT":
                self.state = "DROP_APPROACH"
                drop_approach_coord = [
                    self.drop_location[0],
                    self.drop_location[1],
                    self.current_cell_coord[2] + self.z_offset + self.approach_height
                ]
                self._plan_and_move(drop_approach_coord)

            elif self.state == "DROP_APPROACH":
                self.state = "DROP_ENGAGE"
                drop_engage_coord = [
                    self.drop_location[0],
                    self.drop_location[1],
                    self.current_cell_coord[2] + self.z_offset 
                ]
                self._plan_and_move(drop_engage_coord)
                
            elif self.state == "DROP_ENGAGE":
                self.state = "WAIT_DROP"
                self.wait_timer = 0.25
                self.current_trajectory = None

            elif self.state == "DROP_RETRACT":
                self.state = "IDLE"
                self.is_idle = True
                self.last_completed_cell = self.current_cell_path
                print(f"[{self.name}] Task Complete. Ready for next cell.")
                self.current_trajectory = None