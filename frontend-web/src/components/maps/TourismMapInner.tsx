'use client';

import { MapContainer, Marker, Popup, TileLayer } from 'react-leaflet';
import L from 'leaflet';
import { useEffect } from 'react';
import 'leaflet/dist/leaflet.css';

import type { MapMarker } from '@/lib/types';

const icon = L.divIcon({
  className: '',
  html: `<span style="display:block;width:14px;height:14px;border-radius:9999px;background:#D6A84F;border:2px solid #fff;box-shadow:0 2px 8px rgba(11,61,46,0.35)"></span>`,
  iconSize: [14, 14],
  iconAnchor: [7, 7],
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
