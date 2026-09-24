'use client';

import { MapContainer, Marker, Popup, TileLayer } from 'react-leaflet';
import L from 'leaflet';
import { useEffect } from 'react';
import 'leaflet/dist/leaflet.css';

import type { MapMarker } from '@/lib/types';

const icon = L.icon({
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

export function TourismMapInner({
  markers,
  className = 'h-80',
}: {
  markers: MapMarker[];
  className?: string;
}) {
  useEffect(() => {
    // Fix default icon paths in bundlers
  }, []);

  if (!markers.length) {
    return (
      <div
        className={`flex items-center justify-center rounded-2xl border border-[var(--line)] bg-white text-sm text-[var(--muted)] ${className}`}
      >
        Aucune coordonnée vérifiée pour afficher la carte.
      </div>
    );
  }

  const center: [number, number] = [markers[0].latitude, markers[0].longitude];

  return (
    <div className={`overflow-hidden rounded-2xl border border-[var(--line)] ${className}`}>
      <MapContainer center={center} zoom={markers.length === 1 ? 12 : 7} scrollWheelZoom={false} className="h-full w-full">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {markers.map((m) => (
          <Marker key={m.id} position={[m.latitude, m.longitude]} icon={icon}>
            <Popup>
              <strong>{m.name}</strong>
              {m.category ? <div>{m.category}</div> : null}
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
