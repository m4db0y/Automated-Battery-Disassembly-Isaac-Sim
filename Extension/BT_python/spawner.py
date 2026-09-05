import omni.usd
import omni.kit.commands
from pxr import Gf

class BatterySpawner:
    def __init__(self):
        self.is_spawning = False
        self.battery_type_index = 0 
        
        self.usd_paths = {
            0: r"D:\Battery_Disassembling\Battery\battery_assembly.usd",
            1: r"D:\Battery_Disassembling\Battery\Small_Battery_Assembly.usd"
        }
        
        self.spawn_root = "/World/Spawned_Battery"
        self.spawn_location = (0.0, 0.0, 0.5) 
        self.active_batteries = []
        self.spawn_count = 0
        
        self._create_root_if_needed()
        
    def _create_root_if_needed(self):
        stage = omni.usd.get_context().get_stage()
        if not stage.GetPrimAtPath(self.spawn_root).IsValid():
            omni.kit.commands.execute('CreatePrim', prim_path=self.spawn_root, prim_type='Xform')
            
    def set_spawning(self, state: bool):
        self.is_spawning = state
        if state:
            print("[Spawner] Spawning started.")
            self.spawn_battery() 
        else:
            print("[Spawner] Spawning stopped.")
            
    def set_battery_type(self, index: int):
        self.battery_type_index = index
        print(f"[Spawner] Next battery type set to index: {index}")
        
    def update_step(self, dt):
        pass
                
    def spawn_battery(self):
        stage = omni.usd.get_context().get_stage()
        
        self.active_batteries = [path for path in self.active_batteries if stage.GetPrimAtPath(path).IsValid()]
        
        if len(self.active_batteries) >= 3:
            oldest = self.active_batteries.pop(0)
            omni.kit.commands.execute('DeletePrims', paths=[oldest])
            print(f"[Spawner] Max capacity reached. Deleted oldest battery: {oldest}")
                
        self.spawn_count += 1
        new_prim_path = f"{self.spawn_root}/Battery_Inst_{self.spawn_count}"
        usd_to_spawn = self.usd_paths.get(self.battery_type_index, self.usd_paths[0])
        
        # NATIVE FIX: Set select_prim=False to prevent the gizmo from appearing
        omni.kit.commands.execute(
            'CreateReference',
            usd_context=omni.usd.get_context(),
            path_to=new_prim_path,
            asset_path=usd_to_spawn,
            instanceable=False,
            select_prim=False
        )
        
        omni.kit.commands.execute(
            'TransformPrim',
            path=new_prim_path,
            new_translation=Gf.Vec3d(*self.spawn_location)
        )
        
        self.active_batteries.append(new_prim_path)
        print(f"[Spawner] Deployed new battery at {new_prim_path}")