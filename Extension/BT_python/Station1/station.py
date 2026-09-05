import omni.graph.core as og
import omni.usd

class StationManager:
    def __init__(self, action_graph_path: str = "/World/StationControl", trigger_path: str = "/World/Triggers/Station1_Trigger"):
        self.graph_path = action_graph_path
        self.trigger_path = trigger_path
        
        # Initialize empty cache variables
        self.context = None
        self.start_station1_var = None
        self.script_trigger_var = None
        
    def _cache_variables(self):
        """Finds and caches variables only when the graph is fully valid."""
        graph = og.get_graph_by_path(self.graph_path)
        if graph and graph.is_valid():
            self.context = graph.get_default_graph_context()
            for var in graph.get_variables():
                if var.name == "StartStation1":
                    self.start_station1_var = var
                elif var.name == "ScriptTrigger1":
                    self.script_trigger_var = var

    def is_station_active(self):
        """Reads the 'StartStation1' boolean variable[cite: 15]."""
        if not self.start_station1_var:
            self._cache_variables()
            
        if self.start_station1_var and self.context:
            val = self.start_station1_var.get(self.context)
            if val is not None:
                return bool(val)
        return False
        
    def trigger_conveyor_restart(self):
        """Resets 'StartStation1' for the next battery and toggles 'ScriptTrigger1'[cite: 15]."""
        if not self.script_trigger_var:
            self._cache_variables()
            
        if self.start_station1_var and self.context:
            self.start_station1_var.set(self.context, False)
            print("[StationManager] Reset StartStation1 to False.")
            
        if self.script_trigger_var and self.context:
            current_val = self.script_trigger_var.get(self.context)
            new_val = not current_val if current_val is not None else True
            self.script_trigger_var.set(self.context, new_val)
            print(f"[StationManager] Conveyor triggered! ScriptTrigger1 toggled to {new_val}.")

    def set_trigger_active(self, state: bool):
        """Activates or deactivates the Station 1 trigger prim in the USD stage[cite: 15]."""
        try:
            stage = omni.usd.get_context().get_stage()
            prim = stage.GetPrimAtPath(self.trigger_path)
            if prim.IsValid():
                prim.SetActive(state)
        except Exception as e:
            print(f"[StationManager] Error toggling trigger: {e}")