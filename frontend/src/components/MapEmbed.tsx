"use client";

import { useEffect, useRef, useState } from "react";

interface Marker {
  lat: number;
  lng: number;
  label: string;
}

interface MapEmbedProps {
  center?: [number, number];
  zoom?: number;
  markers?: Marker[];
}

export default function MapEmbed({ center, zoom = 14, markers }: MapEmbedProps) {
  const [L, setL] = useState<any>(null);
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const idRef = useRef(`map-${Math.random().toString(36).slice(2)}`);

  useEffect(() => {
    const existing = document.querySelector('link[href*="leaflet"]');
    if (!existing) {
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
      document.head.appendChild(link);
    }
    import("leaflet").then((leaflet) => setL(leaflet.default));
  }, []);

  useEffect(() => {
    if (!L || !mapRef.current) return;

    if (mapInstanceRef.current) {
      mapInstanceRef.current.remove();
      mapInstanceRef.current = null;
    }

    const mapCenter = center || [51.2465, 22.558];
    const map = L.map(mapRef.current).setView(mapCenter, zoom);
    mapInstanceRef.current = map;

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OSM",
    }).addTo(map);

    const icon = L.divIcon({
      html: `<div style="background:#E30613;width:14px;height:14px;border-radius:50%;border:3px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.4)"></div>`,
      className: "",
      iconSize: [14, 14],
      iconAnchor: [7, 7],
    });

    if (markers && markers.length > 0) {
      markers.forEach((m) => {
        L.marker([m.lat, m.lng], { icon })
          .addTo(map)
          .bindPopup(`<strong>${m.label}</strong>`)
          .openPopup();
      });
    } else {
      // Load all locations from API
      fetch("/api/locations")
        .then((r) => r.json())
        .then((d) => {
          (d.locations || []).forEach((loc: any) => {
            L.marker([loc.lat, loc.lng], { icon })
              .addTo(map)
              .bindPopup(`<strong>${loc.name}</strong><br><span style="font-size:12px;color:#666">${loc.service_count} usług</span>`);
          });
        })
        .catch(() => {});
    }

    setTimeout(() => map.invalidateSize(), 100);

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, [L, center, zoom, markers]);

  return <div ref={mapRef} className="w-full h-full" />;
}
