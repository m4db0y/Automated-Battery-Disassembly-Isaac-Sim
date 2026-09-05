import omni.graph.core as og
import omni.usd

class StationManager:
    def __init__(self, action_graph_path: str = "/World/StationControl", trigger_path: str = "/World/Triggers/Station2_Trigger"):
        self.graph_path = action_graph_path
        self.trigger_path = trigger_path
        
        self.context = None
        self.start_station2_var = None
        self.script_trigger2_var = None
        self.error_printed = False 
        
    def _cache_variables(self):
        graph = og.get_graph_by_path(self.graph_path)
        if graph and graph.is_valid():
            self.context = graph.get_default_graph_context()
            for var in graph.get_variables():
                if var.name == "StartStation2":
                    self.start_station2_var = var
                elif var.name == "ScriptTrigger2":
                    self.script_trigger2_var = var
            
            if not self.start_station2_var and not self.error_printed:
                print(f"\n[STATION 2 ERROR] Found Action Graph at '{self.graph_path}', but it DOES NOT have a variable named 'StartStation2'. Check spelling.")
                self.error_printed = True
        else:
            if not self.error_printed:
                print(f"\n[STATION 2 ERROR] Could not find an Action Graph at '{self.graph_path}'.")
                self.error_printed = True

    def is_station_active(self):
        if not self.start_station2_var:
            self._cache_variables()
            
        if self.start_station2_var and self.context:
            val = self.start_station2_var.get(self.context)
            if val is not None:
                return bool(val)
        return False
        
    def trigger_conveyor_restart(self):
        if not self.script_trigger2_var:
            self._cache_variables()
            
        if self.start_station2_var and self.context:
            self.start_station2_var.set(self.context, False)
            print("[StationManager2] Reset StartStation2 to False.")
            
        if self.script_trigger2_var and self.context:
            current_val = self.script_trigger2_var.get(self.context)
            new_val = not current_val if current_val is not None else True
            self.script_trigger2_var.set(self.context, new_val)
            print(f"[StationManager2] Conveyor triggered! ScriptTrigger2 toggled to {new_val}.")

    def set_trigger_active(self, state: bool):
        try:
            stage = omni.usd.get_context().get_stage()
            prim = stage.GetPrimAtPath(self.trigger_path)
            if prim.IsValid():
                prim.SetActive(state)
        except Exception as e:
            print(f"[StationManager2] Error toggling trigger: {e}")