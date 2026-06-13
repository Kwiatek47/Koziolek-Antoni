# Animacja koziołka

Gotowe pliki do wrzucenia we frontend.

## Podgląd lokalny

```bash
open frontend/public/animacja/podglad_animacji.html
```

## Użycie w Next.js

```tsx
<img src="/animacja/koziolek_biega.gif" alt="Koziołek biega" />
```

Pojedyncze klatki: `/animacja/koziolek_klatki/klatka_1.png` … `klatka_4.png`

## Regeneracja GIF-a

```bash
pip install Pillow
python3 frontend/public/animacja/generuj_animacje_koziolka.py
```
