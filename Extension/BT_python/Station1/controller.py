from .robot import RobotController
from .vision import VisionProcessor
from .camera import StationCamera
from .station import StationManager

class Station1Controller:
    def __init__(self):
        self.station = StationManager(
            action_graph_path="/World/StationControl",
            trigger_path="/World/Triggers/Station1_Trigger" 
        ) 
        self.camera = StationCamera("/World/Camera/Camera_S1")
        self.vision = VisionProcessor()
        
        self.left_robot = None
        self.right_robot = None
        
        self.process_started = False
        self.robots_announced = False 
        self.robots_initialized = False
        
        self.processed_screws = set()

    def _setup_robots(self):
        self.left_robot = RobotController(
            prim_path="/World/Fanuc_Left", 
            name="Left_Robot",
            side="left",
            base_translation=[-8.06, 1.5, 2.0], 
            drop_location=[-9.4, 1.75, 0.0]     
        )
        
        self.right_robot = RobotController(
            prim_path="/World/Fanuc_Right", 
            name="Right_Robot",
            side="right",
            base_translation=[-7.94, -1.5, 2.0], 
            drop_location=[-6.6, -1.75, 0.0]     
        )

    def on_physics_step(self, step_size, e_stop=False):
        if self.left_robot is None or self.right_robot is None:
            self._setup_robots()

        if not self.robots_initialized:
            self.left_robot.initialize()
            self.right_robot.initialize()
            self.robots_initialized = True
            return
            
        if self.left_robot.last_completed_screw:
            self.processed_screws.add(self.left_robot.last_completed_screw)
            self.left_robot.last_completed_screw = None
            
        if self.right_robot.last_completed_screw:
            self.processed_screws.add(self.right_robot.last_completed_screw)
            self.right_robot.last_completed_screw = None
            
        # Freeze activation if E-Stop is active
        if not e_stop and self.station.is_station_active() and not self.process_started:
            print("\n[Controller] New battery detected! Station one is starting...")
            self.process_started = True
            self.robots_announced = False
            self.station.set_trigger_active(False)
            
            self.camera.activate()
            screw_data = self.camera.capture_screw_locations(self.processed_screws)
            self.camera.deactivate()
            self.vision.process_screws(screw_data)
            
        if self.process_started:
            left_assigned = False
            right_assigned = False
            
            # Prevent new task assignments during E-Stop
            if not e_stop:
                if self.left_robot.is_idle:
                    left_data = self.vision.get_next_target_left()
                    if left_data is not None:
                        self.left_robot.assign_task(left_data)
                        left_assigned = True
                        
                if self.right_robot.is_idle:
                    right_data = self.vision.get_next_target_right()
                    if right_data is not None:
                        self.right_robot.assign_task(right_data)
                        right_assigned = True

            if not self.robots_announced and (left_assigned or right_assigned):
                print("[Controller] Robots starting multi-step disassembly sequence.")
                self.robots_announced = True
            
            # Pass E-Stop to robots
            self.left_robot.update_step(step_size, e_stop)
            self.right_robot.update_step(step_size, e_stop)
                    
            if not e_stop and not self.vision.is_work_remaining() and self.left_robot.is_idle and self.right_robot.is_idle:
                print("[Controller] Cycle complete. Activating conveyor.")
                self.station.trigger_conveyor_restart()
                self.process_started = False 
                self.robots_announced = False

    def cleanup(self):
        self.left_robot = None
        self.right_robot = None
        self.robots_initialized = False
        self.process_started = False
        self.processed_screws.clear()