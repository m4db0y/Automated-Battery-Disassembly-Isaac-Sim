from .station_4 import StationManager

class Station4Controller:
    def __init__(self):
        # 1. Manager for Station 4
        self.station = StationManager(
            action_graph_path="/World/StationControl",
            trigger_path="/World/Triggers/Station4_Trigger" 
        ) 
        
        # 2. Handshake Manager: Uses the EXACT SAME local class to reactivate Station 3
        self.station3_manager = StationManager(
            action_graph_path="/World/StationControl",
            trigger_path="/World/Triggers/Station3_Trigger"
        )
        
        self.process_started = False

    def on_physics_step(self, step_size):
        # Trigger Activation & Immediate Handshake
        if self.station.is_station_active() and not self.process_started:
            print("\n[Controller Station 4] Battery reached Station 4! Reactivating Station 3 trigger...")
            self.process_started = True
            
            # IMMEDIATELY reactivate Station 3 trigger for the next battery
            self.station3_manager.set_trigger_active(True)
            
            # Restart conveyor to let the current battery pass through
            # (This safely resets StartStation4 to False in the Action Graph)
            self.station.trigger_conveyor_restart()
            
            # Instantly reset the state machine so it is ready for the next battery
            self.process_started = False

    def cleanup(self):
        self.process_started = False