import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export async function GET() {
  try {
    const res = await fetch(`${BACKEND_URL}/locations`);
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    // Fallback static data
    return NextResponse.json({
      locations: [
        {
          name: "Ratusz - Urząd Miasta Lublin",
          lat: 51.2481,
          lng: 22.5591,
          departments: ["Kancelaria Prezydenta", "Biuro Rady Miasta"],
          service_count: 14,
          services: [],
        },
        {
          name: "Urząd Miasta - Wieniawska",
          lat: 51.2465,
          lng: 22.554,
          departments: ["Wydział Komunikacji", "Wydział Spraw Administracyjnych"],
          service_count: 187,
          services: [],
        },
        {
          name: "Urząd Miasta - Peowiaków",
          lat: 51.251,
          lng: 22.564,
          departments: ["Wydział Spraw Mieszkaniowych", "Wydział Geodezji"],
          service_count: 25,
          services: [],
        },
        {
          name: "Urząd Miasta - Czechowska",
          lat: 51.248,
          lng: 22.551,
          departments: ["Wydział Ochrony Środowiska"],
          service_count: 54,
          services: [],
        },
        {
          name: "Urząd Miasta - Filaretów",
          lat: 51.232,
          lng: 22.529,
          departments: ["Wydział Komunikacji - oddział"],
          service_count: 171,
          services: [],
        },
        {
          name: "Urząd Miasta - Kleeberga",
          lat: 51.26,
          lng: 22.534,
          departments: ["Wydział Budżetu i Księgowości"],
          service_count: 157,
          services: [],
        },
        {
          name: "Urząd Stanu Cywilnego",
          lat: 51.2495,
          lng: 22.547,
          departments: ["Urząd Stanu Cywilnego"],
          service_count: 12,
          services: [],
        },
        {
          name: "Urząd Miasta - Spokojna",
          lat: 51.2456,
          lng: 22.553,
          departments: ["Wydział Podatków"],
          service_count: 69,
          services: [],
        },
      ],
    });
  }
}
