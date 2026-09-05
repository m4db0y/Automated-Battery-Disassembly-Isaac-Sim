from .robot_2 import RobotController
from .station_2 import StationManager

class Station2Controller:
    def __init__(self):
        self.station = StationManager(
            action_graph_path="/World/StationControl", 
            trigger_path="/World/Triggers/Station2_Trigger"
        ) 
        self.station1_manager = StationManager(
            action_graph_path="/World/StationControl",
            trigger_path="/World/Triggers/Station1_Trigger"
        )
        self.robot = None
        self.process_started = False
        self.robot_initialized = False
        self.processed_covers = set()
        
        # INTERNAL FLAG
        self._cycle_completed = False

    def _setup_robot(self):
        self.robot = RobotController(prim_path="/World/Yaskawa")

    def on_physics_step(self, step_size, e_stop=False):
        if self.robot is None:
            self._setup_robot()

        if not self.robot_initialized:
            self.robot.initialize()
            self.robot_initialized = True
            return
            
        if not e_stop and self.station.is_station_active() and not self.process_started:
            print("\n[Controller Station 2] Battery reached station 2! Starting cover removal sequence...")
            self.process_started = True
            self.station.set_trigger_active(False)
            self.robot.assign_task(self.processed_covers)
            
        if self.process_started:
            self.robot.update_step(step_size, e_stop)
            
            if self.robot.last_completed_cover:
                # Extracts the root battery path (e.g., /World/Spawned_Battery/Battery_Inst_1)
                parts = self.robot.last_completed_cover.split('/')
                if len(parts) >= 4:
                    battery_root = "/".join(parts[:4])
                    self.processed_covers.add(battery_root)
                else:
                    self.processed_covers.add(self.robot.last_completed_cover)
                    
                self.robot.last_completed_cover = None
                    
            if not e_stop and self.robot.is_idle:
                print("[Controller Station 2] Task complete. Restarting conveyor and re-activating Station 1 trigger.")
                self.station.trigger_conveyor_restart()
                self.station1_manager.set_trigger_active(True)
                self.process_started = False 
                
                # SET THE FLAG TRUE WHEN FINISHED
                self._cycle_completed = True 

    def check_and_reset_spawn_flag(self):
        """Securely reads the flag and instantly resets it so it only fires once."""
        if self._cycle_completed:
            self._cycle_completed = False
            return True
        return False

    def cleanup(self):
        self.robot = None
        self.robot_initialized = False
        self.process_started = False
        self.processed_covers.clear()
        self._cycle_completed = False