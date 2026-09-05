import omni.ui as ui
import omni.graph.core as og

from .spawner import BatterySpawner
from .Station1.controller import Station1Controller
from .Station2.controller_2 import Station2Controller 
from .Station3.controller_3 import Station3Controller 
from .Station4.controller_4 import Station4Controller 

class UIBuilder:
    def __init__(self):
        self.spawner = BatterySpawner() 
        self.is_e_stop = False
        
        self.station1_controller = Station1Controller()
        self.station2_controller = Station2Controller()
        self.station3_controller = Station3Controller()
        self.station4_controller = Station4Controller()

    def _set_action_graph_var(self, var_name: str, value: bool):
        graph = og.get_graph_by_path("/World/StationControl")
        if graph and graph.is_valid():
            ctx = graph.get_default_graph_context()
            for var in graph.get_variables():
                if var.name == var_name:
                    var.set(ctx, value)
                    return
        print(f"[UI ERROR] Could not find Action Graph variable: {var_name}")

    def _on_start_spawning(self):
        if not self.is_e_stop:
            self.spawner.set_spawning(True)

    def _on_stop_spawning(self):
        self.spawner.set_spawning(False)

    def _on_e_stop(self):
        print("\n!!! EMERGENCY STOP ACTIVATED !!!")
        self.is_e_stop = True
        self.spawner.set_spawning(False)
        self._set_action_graph_var("EmergencyStop", True)
        self._set_action_graph_var("Start", False)

    def _on_resume(self):
        print("\n>>> SYSTEM RESUMED <<<")
        self.is_e_stop = False
        self._set_action_graph_var("EmergencyStop", False)
        self._set_action_graph_var("Start", True)
        
    def _on_battery_type_changed(self, model, item):
        index = model.get_item_value_model().as_int
        self.spawner.set_battery_type(index)

    def on_physics_step(self, step: float):
        dt = float(step) if isinstance(step, (int, float)) else 1.0 / 60.0
        
        self.spawner.update_step(dt)
        
        self.station1_controller.on_physics_step(dt, e_stop=self.is_e_stop)
        self.station2_controller.on_physics_step(dt, e_stop=self.is_e_stop)
        self.station3_controller.on_physics_step(dt, e_stop=self.is_e_stop)
        self.station4_controller.on_physics_step(dt)

        # STRICT HANDSHAKE: This will only evaluate as True exactly one time per cycle
        if self.station2_controller.check_and_reset_spawn_flag():
            if self.spawner.is_spawning and not self.is_e_stop:
                self.spawner.spawn_battery()

    def cleanup(self):
        if hasattr(self, "station1_controller"): self.station1_controller.cleanup()
        if hasattr(self, "station2_controller"): self.station2_controller.cleanup()
        if hasattr(self, "station3_controller"): self.station3_controller.cleanup()
        if hasattr(self, "station4_controller"): self.station4_controller.cleanup()

    def build_ui(self):
        with ui.VStack(spacing=10):
            with ui.HStack(height=30):
                ui.Label("Next Battery Type:", width=150)
                options = ["Standard Battery", "Small Battery"]
                combo_model = ui.ComboBox(0, *options).model
                combo_model.add_item_changed_fn(self._on_battery_type_changed)
                
            ui.Spacer(height=10)
                
            with ui.HStack(height=40, spacing=5):
                ui.Button("Start Spawning", clicked_fn=self._on_start_spawning, style={"background_color": 0xFF00AA00})
                ui.Button("Stop Spawning", clicked_fn=self._on_stop_spawning, style={"background_color": 0xFFAAAAAA})
                
            ui.Spacer(height=20)
            
            ui.Button("EMERGENCY STOP", clicked_fn=self._on_e_stop, height=50, style={"background_color": 0xFF0000AA, "color": 0xFFFFFFFF})
            ui.Button("Resume Work", clicked_fn=self._on_resume, height=40, style={"background_color": 0xFF0055AA})

    def on_menu_callback(self):
        pass
    def on_timeline_event(self, event):
        pass
    def on_stage_event(self, event):
        pass