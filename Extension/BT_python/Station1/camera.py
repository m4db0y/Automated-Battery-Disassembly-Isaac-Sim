import omni.usd
from pxr import Usd, UsdGeom

class StationCamera:
    def __init__(self, camera_prim_path: str = "/World/Camera/Camera_S1"):
        self.camera_path = camera_prim_path
        
    def activate(self):
        """Wakes up the camera for inference."""
        print(f"[StationCamera] Activating camera at {self.camera_path}")
        
    def capture_screw_locations(self, ignore_list):
        """
        Scans ONLY inside the /World/Spawned_Battery Xform.
        Skips any prim paths present in the ignore_list.
        """
        stage = omni.usd.get_context().get_stage()
        screw_data = []
        xform_cache = UsdGeom.XformCache(omni.timeline.get_timeline_interface().get_current_time())
        
        spawn_root = stage.GetPrimAtPath("/World/Spawned_Battery")
        if not spawn_root.IsValid():
            print("[StationCamera] ERROR: /World/Spawned_Battery not found!")
            return []

        # Usd.PrimRange restricts the search domain strictly to the battery children
        for prim in Usd.PrimRange(spawn_root):
            prim_path = prim.GetPath().pathString
            
            # 1. Check Python Memory Tag
            if prim_path in ignore_list:
                continue
                
            prim_name = prim.GetName().lower()
            name_has_screw = "screw" in prim_name
            
            tag_has_screw = False
            for prop in prim.GetProperties():
                if "semantic" in prop.GetName().lower():
                    val = prop.Get()
                    if val and "screw" in str(val).lower():
                        tag_has_screw = True
                        break

            if name_has_screw and tag_has_screw and prim.IsA(UsdGeom.Xformable):
                world_matrix = xform_cache.GetLocalToWorldTransform(prim)
                translation = world_matrix.ExtractTranslation()
                
                coord = [float(translation[0]), float(translation[1]), float(translation[2])]
                screw_data.append((prim_path, coord))
                
        print(f"[StationCamera] Successfully captured {len(screw_data)} new screws.")
        return screw_data
        
    def deactivate(self):
        """Shuts down the camera logic to save compute resources."""
        print(f"[StationCamera] Deactivating camera at {self.camera_path}")