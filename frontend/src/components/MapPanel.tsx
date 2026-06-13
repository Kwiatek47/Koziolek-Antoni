"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";

const MapContainer = dynamic(
  () => import("react-leaflet").then((mod) => mod.MapContainer),
  { ssr: false }
);
const TileLayer = dynamic(
  () => import("react-leaflet").then((mod) => mod.TileLayer),
  { ssr: false }
);
const Marker = dynamic(
  () => import("react-leaflet").then((mod) => mod.Marker),
  { ssr: false }
);
const Popup = dynamic(
  () => import("react-leaflet").then((mod) => mod.Popup),
  { ssr: false }
);

interface Location {
  name: string;
  lat: number;
  lng: number;
  departments: string[];
  service_count: number;
  services?: Array<{ title: string; url: string }>;
}

interface MapPanelProps {
  highlight?: string | null;
}

export default function MapPanel({ highlight }: MapPanelProps) {
  const [locations, setLocations] = useState<Location[]>([]);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    fetch("/api/locations")
      .then((r) => r.json())
      .then((data) => setLocations(data.locations || []))
      .catch(() => {});
  }, []);

  if (!mounted) {
    return (
      <div className="flex-1 flex items-center justify-center bg-lublin-surface">
        <p className="text-lublin-muted">Ładowanie mapy...</p>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="p-4 border-b border-lublin-border bg-white">
        <h2 className="text-xl font-bold">Mapa urzędów</h2>
        <p className="text-sm text-lublin-muted">
          Kliknij punkt, aby zobaczyć jakie sprawy można tam załatwić
        </p>
      </div>
      <div className="flex-1 relative">
        <link
          rel="stylesheet"
          href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
        />
        <MapContainer
          center={[51.2465, 22.5580]}
          zoom={14}
          className="h-full w-full z-0"
          scrollWheelZoom={true}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {locations.map((loc, i) => (
            <Marker key={i} position={[loc.lat, loc.lng]}>
              <Popup maxWidth={320}>
                <div className="font-sans">
                  <h3 className="font-bold text-base mb-1">{loc.name}</h3>
                  <p className="text-sm text-gray-600 mb-2">
                    {loc.service_count} usług dostępnych
                  </p>
                  <div className="text-xs space-y-1 mb-2">
                    {loc.departments.map((d, j) => (
                      <span
                        key={j}
                        className="inline-block bg-green-50 text-green-800 px-2 py-0.5 rounded mr-1 mb-1"
                      >
                        {d}
                      </span>
                    ))}
                  </div>
                  {loc.services && loc.services.length > 0 && (
                    <div className="border-t pt-2 mt-2">
                      <p className="text-xs font-medium mb-1">Przykładowe usługi:</p>
                      {loc.services.slice(0, 3).map((s, j) => (
                        <a
                          key={j}
                          href={s.url}
                          target="_blank"
                          rel="noopener"
                          className="text-xs text-green-700 hover:underline block truncate"
                        >
                          • {s.title}
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
    </div>
  );
}
