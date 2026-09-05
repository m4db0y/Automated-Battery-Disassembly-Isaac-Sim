import omni.ext
import omni.timeline
import omni.ui as ui
import carb.eventdispatcher
import omni.usd

from .ui_builder import UIBuilder

class FactoryExtension(omni.ext.IExt):
    def on_startup(self, ext_id):
        self.ext_id = ext_id
        
        # 1. Create a basic UI Window 
        self._window = ui.Window("Battery Disassembly", width=300, height=150, visible=True)
        
        # 2. Initialize the UI Builder (which holds your Station1 logic)
        self.ui_builder = UIBuilder()
        
        # 3. Setup Event Subscriptions (Physics, Play, Pause, Stop)
        self._setup_events()
        
        # 4. Build the initial (empty) UI
        with self._window.frame:
            self.ui_builder.build_ui()

    def _setup_events(self):
        self._usd_context = omni.usd.get_context()
        self._timeline = omni.timeline.get_timeline_interface()
        events = carb.eventdispatcher.get_eventdispatcher()
        
        # Subscribe to Timeline Play/Stop using explicit keyword arguments
        self._play_sub = events.observe_event(
            event_name=omni.timeline.GLOBAL_EVENT_PLAY, 
            on_event=self._on_play
        )
        self._stop_sub = events.observe_event(
            event_name=omni.timeline.GLOBAL_EVENT_STOP, 
            on_event=self._on_stop
        )
        
        # Subscribe to Stage Open/Close using explicit keyword arguments
        self._stage_open_sub = events.observe_event(
            event_name=self._usd_context.stage_event_name(omni.usd.StageEventType.OPENED), 
            on_event=self._on_stage_event
        )
        self._stage_closed_sub = events.observe_event(
            event_name=self._usd_context.stage_event_name(omni.usd.StageEventType.CLOSED), 
            on_event=self._on_stage_event
        )
        
        self._physics_sub = None

    def _on_play(self, event):
        """Starts the physics step loop when you press Play."""
        import omni.physics.core
        physics_interface = omni.physics.core.get_physics_simulation_interface()
        self._physics_sub = physics_interface.subscribe_physics_on_step_events(
            pre_step=False, order=0, on_update=self._on_physics_step
        )
        self.ui_builder.on_timeline_event(event)

    def _on_stop(self, event):
        """Stops the physics loop when you press Stop."""
        self._physics_sub = None
        self.ui_builder.on_timeline_event(event)

    def _on_physics_step(self, step, context):
        """Passes the physics step to the UI Builder & Station1 Controller."""
        self.ui_builder.on_physics_step(step)

    def _on_stage_event(self, event):
        self._physics_sub = None
        self.ui_builder.cleanup()
        self.ui_builder.on_stage_event(event)

    def on_shutdown(self):
        """Cleans up everything when the extension is closed."""
        self._physics_sub = None
        self._play_sub = None
        self._stop_sub = None
        self._stage_open_sub = None
        self._stage_closed_sub = None
        
        if self._window:
            self._window.destroy()
            self._window = None
            
        self.ui_builder.cleanup()