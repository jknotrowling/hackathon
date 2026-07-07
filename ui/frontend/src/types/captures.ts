export interface FlightCapture {
  id: number;
  flight_id: number;
  waypoint_index: number;
  location: {
    type: 'Point';
    coordinates: [number, number];
  };
  image_url: string;
}
