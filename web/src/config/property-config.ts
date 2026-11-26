export interface PropertyMarketingConfig {
  projectName: string;
  tagline: string;
  address: string;
  price: string;
  statusBadge: string;
  agent: {
    name: string;
    title: string;
    agency: string;
    phone: string;
    email: string;
  };
  /** Verified architectural counts from floorplan-spec.json */
  verifiedMetrics: {
    landAreaM2: number;
    landAreaSqft: number;
    buildingFootprintM2: number;
    usableInteriorM2: number;
    usableInteriorSqft: number;
    bedrooms: number;
    bathrooms: number;
    carportVehicles: number;
    ceilingHeightMm: number;
  };
  /** Guided tour room storytelling mapped by waypoint ID */
  tourNarratives: Record<
    string,
    {
      roomName: string;
      areaM2: number;
      areaSqft: number;
      designFeature: string;
      sellingPoint: string;
    }
  >;
}

/**
 * Editable property presentation & marketing metadata.
 * Update address, price, and agent contact values freely without altering
 * the verified architectural geometry in `public/assets/floorplan-spec.json`.
 */
export const PROPERTY_CONFIG: PropertyMarketingConfig = {
  projectName: 'Villa Aurelia 123',
  tagline: 'Modern Tropical Single-Story Luxury Residence',
  address: 'Jl. Kemang Selatan Residences No. 123 (Editable Site Address)',
  price: '$485,000 USD (Editable Asking Price)',
  statusBadge: 'Private Collection · Ready to Explore',
  agent: {
    name: 'Elena Vance, AIA',
    title: 'Senior Architectural Property Advisor',
    agency: 'Aurelia Bespoke Realty',
    phone: '+62 811-0000-0123',
    email: 'concierge@aurelia-residences.example',
  },
  verifiedMetrics: {
    landAreaM2: 123.44,
    landAreaSqft: 1328.74,
    buildingFootprintM2: 80.17,
    usableInteriorM2: 69.43,
    usableInteriorSqft: 747.31,
    bedrooms: 2,
    bathrooms: 2,
    carportVehicles: 1,
    ceilingHeightMm: 3000,
  },
  tourNarratives: {
    'WP-01': {
      roomName: 'Street Approach & Front Garden',
      areaM2: 11.59,
      areaSqft: 124.75,
      designFeature: 'Stepped facade with fluted walnut accent cladding & teak-slat carport pergola',
      sellingPoint: 'Generous 35% open outdoor ratio across carport, front garden, and rear courtyard.',
    },
    'WP-02': {
      roomName: 'Main Entrance & Foyer',
      areaM2: 3.86,
      areaSqft: 41.55,
      designFeature: '1,000 mm walnut pivot door flanked by a full-height frosted daylight sidelight',
      sellingPoint: 'Composed arrival sequence with built-in millwork bench and immediate visual calm.',
    },
    'WP-03': {
      roomName: 'Entry Gallery & Circulation Spine',
      areaM2: 5.02,
      areaSqft: 54.03,
      designFeature: '1,100 mm gallery hallway linking public living spaces and private bedrooms',
      sellingPoint: 'Zero wasted corridor space with clear acoustic separation between social and sleeping wings.',
    },
    'WP-04': {
      roomName: 'Open-Plan Dining & Modern Kitchen',
      areaM2: 12.24,
      areaSqft: 131.75,
      designFeature: '6-seat dining area paired with L-shaped quartz kitchen, induction hob & integrated fridge',
      sellingPoint: 'Effortless hosting with direct sightlines to the living room and rear outdoor terrace.',
    },
    'WP-05': {
      roomName: 'Open-Plan Living Room',
      areaM2: 11.4,
      areaSqft: 122.71,
      designFeature: '3.0 m clear ceilings, fluted media wall & 2.8 m 3-panel aluminum sliding glass doors',
      sellingPoint: 'True tropical indoor-outdoor living that expands seamlessly onto the oiled teak deck.',
    },
    'WP-06': {
      roomName: 'Rear Outdoor Terrace & Zen Garden',
      areaM2: 16.46,
      areaSqft: 177.17,
      designFeature: '1,200 mm cantilevered timber soffit overhang, teak decking & Japanese maple courtyard',
      sellingPoint: 'Private sheltered outdoor lounge for sunset entertaining and cross-ventilation.',
    },
    'WP-07': {
      roomName: 'Master Bedroom Suite',
      areaM2: 11.88,
      areaSqft: 127.88,
      designFeature: 'King platform bed, 2.4 m built-in sliding wardrobe & 2.2 m panoramic garden window',
      sellingPoint: 'Quiet rear sanctuary overlooking lush greenery away from street noise.',
    },
    'WP-08': {
      roomName: 'Master Ensuite Bathroom',
      areaM2: 3.16,
      areaSqft: 34.01,
      designFeature: 'Frameless walk-in rain shower, floating stone vanity, backlit mirror & frosted awning window',
      sellingPoint: 'Spa-inspired natural ventilation and travertine wet-area detailing.',
    },
    'WP-09': {
      roomName: 'Bedroom 2',
      areaM2: 8.42,
      areaSqft: 90.63,
      designFeature: 'Queen bed, integrated wardrobe, study desk & high-sill privacy window over carport',
      sellingPoint: 'Bright, well-proportioned secondary suite ideal for family or executive home office.',
    },
    'WP-10': {
      roomName: 'Programmer Studio & Tech Workspace',
      areaM2: 8.52,
      areaSqft: 91.71,
      designFeature: '2.5 m walnut standing desk by the 1.6 m garden picture window with 49" ultrawide + vertical coding monitors, homelab shelf & reading lounge',
      sellingPoint: 'Purpose-built natural-light software engineering sanctuary overlooking the front garden specimen tree.',
    },
  },
};
