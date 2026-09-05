import numpy as np
import omni.usd
import omni.kit.app
import omni.kit.commands
from pxr import Usd, UsdGeom, Gf
from isaacsim.robot_motion.cumotion import (
    load_cumotion_robot,
    CumotionWorldInterface,
    GraphBasedMotionPlanner
)
from isaacsim.core.prims import SingleArticulation
from isaacsim.core.utils.types import ArticulationAction

class RobotController:
    def __init__(self, prim_path: str = "/World/Yaskawa"):
        self.prim_path = prim_path
        self.robot = None
        self.cumotion_robot = None
        self.world = None
        self.planner = None
        self.app = omni.kit.app.get_app()
        
        self.is_idle = True
        self.state = "IDLE"
        self.current_cover_path = None
        self.last_completed_cover = None
        
        self.JOINT_NAMES = ["joint_1_s", "joint_2_l", "joint_3_u", "joint_4_r", "joint_5_b", "joint_6_t"]
        self.MAX_VELOCITIES = [3.66519116, 3.66519116, 4.62512252, 7.33038233, 7.85398110, 12.56637061]
        self.MAX_ACCELERATIONS = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
        
        self.QUAT1 = self._normalize_quaternion(np.array([1.0, 0.0, 0.0, 1.0]))
        self.QUAT2 = self._normalize_quaternion(np.array([0.0, 0.0, 0.0, 1.0]))
        self.QUAT3 = self._normalize_quaternion(np.array([-1.0, 0.0, 0.0, 1.0]))
        
        self.targets = [
            ("Step 1", np.array([1.5, 0.0, 0.78]), self.QUAT1),
            ("Step 2", np.array([1.5, 0.0, -0.02]), self.QUAT1),
            ("Step 3", np.array([1.5, 0.0, 0.78]), self.QUAT1),
            ("Step 4", np.array([-1.5, 0.5, 0.78]), self.QUAT3),
            ("Step 5", np.array([-1.5, 0.5, 0.0]), self.QUAT3)
        ]
        
        self.current_step_idx = 0
        self.current_jt = None
        self.t = 0.0
        self.dt = 1.0 / 60.0
        self.last_command = None
        self.wait_timer = 0.0
        self.dummy_b1_path = "/World/Yaskawa/link_6_t/flange/tool0/B1_Cover"
        self.dummy_b2_path = "/World/Yaskawa/link_6_t/flange/tool0/B2_Cover"
        self.active_dummy_path = None
        self.spawned_cases_history = []

    def _normalize_quaternion(self, q):
        q = np.asarray(q, dtype=np.float64)
        norm = np.linalg.norm(q)
        if norm < 1e-8: raise ValueError("Quaternion has zero magnitude.")
        return q / norm

    def initialize(self):
        if self.robot is not None: return
        self.cumotion_robot = load_cumotion_robot(
            directory=r"D:\BatteryDT\Yaskawa",
            urdf_filename="Yaskawa.urdf",
            xrdf_filename="Yaskawa.xrdf"
        )
        self.world = CumotionWorldInterface()
        self.planner = GraphBasedMotionPlanner(
            cumotion_robot=self.cumotion_robot,
            cumotion_world_interface=self.world,
            tool_frame="link_6_t"
        )
        self.robot = SingleArticulation(self.prim_path)
        self.robot.initialize()

    def _closest_angle(self, target_angle, reference_angle):
        two_pi = 2.0 * np.pi
        while target_angle - reference_angle > np.pi: target_angle -= two_pi
        while target_angle - reference_angle < -np.pi: target_angle += two_pi
        return target_angle

    def _unwrap_joints(self, target_joints, reference_joints):
        target_joints = np.asarray(target_joints, dtype=np.float64).copy()
        reference_joints = np.asarray(reference_joints, dtype=np.float64)
        for i in range(len(target_joints)):
            target_joints[i] = self._closest_angle(target_joints[i], reference_joints[i])
        return target_joints

    def _spawn_dropped_cover(self):
        stage = omni.usd.get_context().get_stage()
        import time
        
        unique_id = int(time.time() * 1000)
        
        if self.active_dummy_path == self.dummy_b1_path:
            usd_file = r"D:\Battery_Disassembling\Battery\DB1_Cover.usd"
            spawn_path = f"/World/B1/Dropped_B1_{unique_id}"
        elif self.active_dummy_path == self.dummy_b2_path:
            usd_file = r"D:\Battery_Disassembling\Battery\DB2_Cover.usd"
            spawn_path = f"/World/B2/Dropped_B2_{unique_id}"
        else:
            return

        # Define an empty Xform and link your local USD file to it
        spawned_prim = stage.DefinePrim(spawn_path, "Xform")
        spawned_prim.GetReferences().AddReference(usd_file)
        self.spawned_cases_history.append(spawn_path)

        if len(self.spawned_cases_history) > 2:
            # Pop the oldest path from the beginning of the list
            oldest_path = self.spawned_cases_history.pop(0)
            # Remove it cleanly from the USD stage
            stage.RemovePrim(oldest_path)

    def _find_cover_in_workspace(self, ignore_list):
        stage = omni.usd.get_context().get_stage()
        spawn_root = stage.GetPrimAtPath("/World/Spawned_Battery")
        if not spawn_root.IsValid(): return None
            
        # Iterate over the battery instances directly
        for child in spawn_root.GetChildren():
            battery_path = child.GetPath().pathString
            
            # If this entire battery is in the ignore list, skip to the next one
            if battery_path in ignore_list:
                continue
                
            # This is the active, unprocessed battery at the station. Find its cover.
            for prim in Usd.PrimRange(child):
                if "cover" in prim.GetName().lower() and prim.IsA(UsdGeom.Xformable):
                    return prim.GetPath().pathString
                    
        return None

    def assign_task(self, ignore_list):
        found_cover_path = self._find_cover_in_workspace(ignore_list)
        if found_cover_path:
            self.current_cover_path = found_cover_path
            
            # Determine the dummy based on the name of the cover prim
            cover_name_lower = found_cover_path.lower()
            if "small" in cover_name_lower:
                self.active_dummy_path = self.dummy_b2_path
            else:
                self.active_dummy_path = self.dummy_b1_path
                
            print(f"\n[Robot 2] Current Battery Cover Found: {self.current_cover_path}")
            print(f"[Robot 2] Assigned Dummy: {self.active_dummy_path}\n")
                
            self.is_idle = False
            self.current_step_idx = 0
            self.state = "PLANNING"
        else:
            self.is_idle = True

    def _plan_current_step(self):
        name, target, quaternion = self.targets[self.current_step_idx]
        raw_joints = self.robot.get_joint_positions()
        if raw_joints is None: return False 
            
        current_joints = np.asarray(raw_joints, dtype=np.float64).copy()
        
        # 1. WRAP THE SEED JOINTS: Force the IK planner to only see angles between -pi and pi
        # This completely stops the 900-degree wind-up loops
        seed_joints = np.arctan2(np.sin(current_joints), np.cos(current_joints))
        
        traj = self.planner.plan_to_pose_target(seed_joints, target, quaternion)
        
        if traj is None:
            self.state = "FAILED"
            return False
            
        self.current_jt = traj.to_minimal_time_joint_trajectory(
            max_velocities=self.MAX_VELOCITIES, max_accelerations=self.MAX_ACCELERATIONS,
            robot_joint_space=self.JOINT_NAMES, active_joints=self.JOINT_NAMES
        )
        self.t = 0.0
        
        # 2. KEEP RAW JOINTS FOR EXECUTION: Ensure the physical robot does not snap
        self.last_command = current_joints
        self.state = "EXECUTING"
        return True

    def update_step(self, dt, e_stop=False):
        if self.is_idle or self.robot is None: return

        if self.state == "FAILED":
            self.is_idle = True
            self.state = "IDLE"
            return

        if self.state == "PLANNING":
            if not e_stop: self._plan_current_step()
            return

        if self.state == "EXECUTING":
            if self.current_jt is not None and self.t <= self.current_jt.duration:
                state = self.current_jt.get_target_state(self.t)
                if state is not None:
                    positions = np.asarray(state.joints.positions, dtype=np.float64).copy()
                    positions = self._unwrap_joints(positions, self.last_command)
                    self.robot.apply_action(ArticulationAction(joint_positions=positions))
                    self.last_command = positions
                
                if not e_stop: self.t += dt
            else:
                if not e_stop:
                    name = self.targets[self.current_step_idx][0]
                    stage = omni.usd.get_context().get_stage()
                    
                    if name == "Step 2" and self.current_cover_path:
                        stage = omni.usd.get_context().get_stage()
                        
                        # 1. UNLOCK ALL INSTANCES IN THE CHAIN
                        curr_prim = stage.GetPrimAtPath(self.current_cover_path)
                        while curr_prim.IsValid() and "Spawned_Battery" in curr_prim.GetPath().pathString:
                            if curr_prim.IsInstanceable():
                                curr_prim.SetInstanceable(False)
                            curr_prim = curr_prim.GetParent()

                        # 2. RECURSIVELY HIDE EVERY NESTED MESH INSIDE THE COVER
                        cover_prim = stage.GetPrimAtPath(self.current_cover_path)
                        if cover_prim.IsValid(): 
                            omni.kit.commands.execute('TransformPrimSRT',
                                path=self.current_cover_path,
                                new_scale=Gf.Vec3d(0.001, 0.001, 0.001)
                            )
                            
                        # 3. SHOW ROBOT DUMMY
                        if self.active_dummy_path:
                            dummy_prim = stage.GetPrimAtPath(self.active_dummy_path)
                            if dummy_prim.IsValid(): 
                                omni.kit.commands.execute('TransformPrimSRT',
                                    path=self.active_dummy_path,
                                    new_scale=Gf.Vec3d(1.0, 1.0, 1.0)
                                )

                    self.current_step_idx += 1
                    
                    if self.current_step_idx < len(self.targets):
                        self.state = "WAIT_PAUSE"
                        self.wait_timer = 1.0 if name == "Step 2" else 0.2
                    else:
                        if self.active_dummy_path:
                            dummy_prim = stage.GetPrimAtPath(self.active_dummy_path)
                            if dummy_prim.IsValid(): 
                                omni.kit.commands.execute('TransformPrimSRT',
                                    path=self.active_dummy_path,
                                    new_scale=Gf.Vec3d(0.001, 0.001, 0.001)
                                )
                                self._spawn_dropped_cover()
                                
                        self.last_completed_cover = self.current_cover_path
                        self.is_idle = True
                        self.state = "IDLE"
            return

        if self.state == "WAIT_PAUSE":
            if not e_stop: self.wait_timer -= dt
            if self.wait_timer <= 0:
                self.state = "PLANNING"
            return
