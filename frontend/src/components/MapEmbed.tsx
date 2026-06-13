"use client";

import { useEffect, useState } from "react";

interface Location {
  name: string;
  lat: number;
  lng: number;
  departments: string[];
  service_count: number;
}

export default function MapEmbed() {
  const [L, setL] = useState<any>(null);
  const [locations, setLocations] = useState<Location[]>([]);

  useEffect(() => {
    // Load leaflet dynamically
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
    document.head.appendChild(link);

    import("leaflet").then((leaflet) => {
      setL(leaflet.default);
    });

    fetch("/api/locations")
      .then((r) => r.json())
      .then((d) => setLocations(d.locations || []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!L || locations.length === 0) return;

    const container = document.getElementById("map-embed");
    if (!container) return;

    // Clear previous map
    container.innerHTML = "";

    const map = L.map(container).setView([51.2465, 22.558], 14);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap",
    }).addTo(map);

    const icon = L.divIcon({
      html: `<div style="background:#006B3F;width:12px;height:12px;border-radius:50%;border:2px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3)"></div>`,
      className: "",
      iconSize: [12, 12],
      iconAnchor: [6, 6],
    });

    locations.forEach((loc) => {
      L.marker([loc.lat, loc.lng], { icon })
        .addTo(map)
        .bindPopup(
          `<strong>${loc.name}</strong><br><span style="color:#5f6d64;font-size:12px">${loc.service_count} usług</span>`
        );
    });

    return () => {
      map.remove();
    };
  }, [L, locations]);

  return <div id="map-embed" className="w-full h-full" />;
}
