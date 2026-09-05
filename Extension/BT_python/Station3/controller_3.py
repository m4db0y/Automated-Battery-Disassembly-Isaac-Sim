from .robot_3 import RobotController
from .vision_3 import VisionProcessor
from .camera_3 import StationCamera
from .station_3 import StationManager

class Station3Controller:
    def __init__(self):
        self.station = StationManager(
            action_graph_path="/World/StationControl",
            trigger_path="/World/Triggers/Station3_Trigger" 
        ) 
        self.station2_manager = StationManager(
            action_graph_path="/World/StationControl",
            trigger_path="/World/Triggers/Station2_Trigger"
        )
        self.camera = StationCamera("/World/Camera/Camera_S3")
        self.vision = VisionProcessor()
        
        self.robot = None
        self.process_started = False
        self.robot_initialized = False
        self.processed_cells = set()

    def _setup_robot(self):
        self.robot = RobotController(
            prim_path="/World/Kuka", 
            name="Kuka_Robot_S3",
            base_translation=[8.0, -2.0, 2.0], 
            drop_location=[6.5, -2, 0.5]    
        )

    def on_physics_step(self, step_size, e_stop=False):
        if self.robot is None:
            self._setup_robot()

        if not self.robot_initialized:
            self.robot.initialize()
            self.robot_initialized = True
            return
            
        if self.robot.last_completed_cell:
            self.processed_cells.add(self.robot.last_completed_cell)
            self.robot.last_completed_cell = None
            
        if not e_stop and self.station.is_station_active() and not self.process_started:
            print("\n[Controller Station 3] Battery detected! Station 3 is starting cell extraction...")
            self.process_started = True
            self.station.set_trigger_active(False)
            self.station2_manager.set_trigger_active(True)
            
            self.camera.activate()
            cell_data = self.camera.capture_cell_locations(self.processed_cells)
            self.camera.deactivate()
            self.vision.process_cells(cell_data)
            
        if self.process_started:
            if not e_stop and self.robot.is_idle:
                cell_data = self.vision.get_next_target()
                if cell_data is not None:
                    self.robot.assign_task(cell_data)
            
            self.robot.update_step(step_size, e_stop)
                    
            if not e_stop and not self.vision.is_work_remaining() and self.robot.is_idle:
                print("[Controller Station 3] Cycle complete. Activating conveyor.")
                self.station.trigger_conveyor_restart()
                self.process_started = False 

    def cleanup(self):
        self.robot = None
        self.robot_initialized = False
        self.process_started = False
        self.processed_cells.clear()