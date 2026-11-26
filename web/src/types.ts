export type CameraMode = 'exterior' | 'dollhouse' | 'floorplan' | 'firstperson';
export type InteriorStyle = 'warm_luxury' | 'scandinavian' | 'modern';
export type QualityLevel = 'low' | 'medium' | 'high' | 'ultra';
export type FloorFilter = 'all' | '1' | '2';

export interface InteractiveDoorConfig {
  id: string;
  label?: string;
  connects?: string[];
  object_name: string;
  kind: 'hinged' | 'sliding_multi' | 'pocket_sliding';
  pivot_blender?: [number, number, number];
  pivot_threejs?: [number, number, number];
  center_threejs?: [number, number, number];
  closed_aabb_threejs?: [number, number, number, number, number, number];
  open_angle_deg?: number;
  swing_sign?: number;
  slide_axis_threejs?: [number, number, number];
  max_slide_m?: number;
  swing_direction: string;
}

export interface SceneConfig {
  project: string;
  units: string;
  coordinate_convention: string;
  site_bounds_m: {
    width_x: number;
    depth_z: number;
    total_land_area_m2: number;
    building_footprint_m2: number;
    usable_interior_m2: number;
    finished_floor_y: number;
    ceiling_height_m: number;
  };
  assets: {
    blend_source: string;
    architecture: { file: string; objects: number; triangles: number };
    collision: { file: string; objects: number; triangles: number };
    interior_styles: Record<
      InteriorStyle,
      {
        label: string;
        file: string;
        floor_override_material: string;
        objects: number;
        triangles: number;
      }
    >;
  };
  dollhouse_toggle_objects: {
    roof: string[];
    ceilings: string[];
    level2_objects?: string[];
  };
  interactive_doors: InteractiveDoorConfig[];
  lighting_presets: Record<
    string,
    {
      label: string;
      sun_elevation_deg: number;
      sun_azimuth_deg: number;
      sky_intensity: number;
      sun_color_hex: string;
      interior_lights_multiplier: number;
      outdoor_lights_multiplier: number;
      exposure: number;
    }
  >;
  cameras: Record<string, Record<string, unknown>>;
}

export interface TourWaypoint {
  id: string;
  name: string;
  room: string;
  eye_height_m: number;
  blender_position: [number, number, number];
  blender_look_at: [number, number, number];
  threejs_position: [number, number, number];
  threejs_look_at: [number, number, number];
}

export interface TourWaypointsData {
  project: string;
  default_eye_height_m: number;
  walk_speed_mps: number;
  waypoints: TourWaypoint[];
}

export interface RoomSpec {
  id: string;
  name: string;
  short_name: string;
  zone: string;
  floor?: 1 | 2;
  ceiling_height_mm: number;
  floor_material: string;
  polygon: [number, number][];
  sub_rects?: [number, number, number, number][];
  width_mm: number;
  depth_mm: number;
  area_m2: number;
  area_sqft: number;
  label_pos: [number, number];
  notes: string;
}

export interface FurnitureSpec {
  id: string;
  room: string;
  kind: string;
  name: string;
  rect: [number, number, number, number];
  height_mm: number;
  rotation_deg: number;
  material: string;
}

export interface FloorplanSpec {
  meta: Record<string, unknown>;
  site: {
    width_mm: number;
    depth_mm: number;
    total_land_area_m2: number;
    total_land_area_sqft: number;
    total_perimeter_m: number;
  };
  area_summary: Record<string, number>;
  outdoor_zones: Array<{
    id: string;
    name: string;
    type: string;
    floor?: 1 | 2;
    bounds: { x0: number; y0: number; x1: number; y1: number };
    width_mm: number;
    depth_mm: number;
    area_m2: number;
    finish: string;
  }>;
  rooms: RoomSpec[];
  walls: Array<{
    id: string;
    category: string;
    rect: [number, number, number, number];
    thickness_mm: number;
    height_mm: number;
    orientation: 'H' | 'V';
  }>;
  doors: Array<{
    id: string;
    type: string;
    width_mm: number;
    height_mm: number;
    opening: [number, number, number, number];
    swing_direction: string;
  }>;
  windows: Array<{
    id: string;
    type: string;
    width_mm: number;
    height_mm: number;
    sill_height_mm: number;
    opening: [number, number, number, number];
    orientation: string;
  }>;
  furniture: FurnitureSpec[];
  materials: Record<string, { name: string; color_hex: string; roughness: number; metalness: number }>;
}

export interface InspectionInfo {
  title: string;
  category: string;
  roomName: string;
  materialName: string;
  dimensions: string;
  styleLabel: string;
  notes?: string;
}

declare global {
  interface Window {
    __EMBEDDED_ASSETS__?: Record<string, string>;
  }
}
