# NetResearch – Benchmark-Report

Läufe: 285 (Seeds [0]), Updates je Lauf: [1500], ~100k Parameter je Modell. Fehlgeschlagene Läufe: 0.

Score: Klassifikation `(acc-chance)/(1-chance)`, Bits: Exact-Match, Spiele `(Return-Random)/(Experte-Random)`. Werte < 0 = schlechter als Zufall.

## Zusammenfassung (Mittel je Task-Gruppe)

| Modell | patterns | image | text | game | gesamt | Ø Rang | Parameter | Trainzeit [min] |
|---|---|---|---|---|---|---|---|---|
| layer_s | 0.92 | 0.98 | 0.43 | 0.75 | 0.82 | 4.20 | 101k | 134.2 |
| hier_s | 0.88 | 0.96 | 0.43 | 0.64 | 0.75 | 8.10 | 100k | 148.9 |
| layer_i | 0.80 | 0.95 | 0.44 | 0.67 | 0.74 | 6.47 | 97k | 51.3 |
| cnn | 0.64 | 0.98 | 0.38 | 0.78 | 0.73 | 5.93 | 103k | 88.6 |
| bus_mul_s | 0.52 | 0.94 | 0.43 | 0.64 | 0.63 | 8.07 | 100k | 20.4 |
| bus_gate_s | 0.49 | 0.93 | 0.43 | 0.66 | 0.62 | 8.20 | 100k | 22.9 |
| hier_i | 0.55 | 0.93 | 0.41 | 0.61 | 0.62 | 10.43 | 100k | 76.4 |
| bus_add_s | 0.48 | 0.93 | 0.43 | 0.65 | 0.62 | 8.90 | 100k | 19.4 |
| gru | 0.52 | 0.88 | 0.36 | 0.64 | 0.61 | 11.87 | 100k | 16.7 |
| bus_mul_i | 0.49 | 0.92 | 0.42 | 0.64 | 0.61 | 9.40 | 100k | 15.5 |
| bus_film_i | 0.49 | 0.92 | 0.44 | 0.63 | 0.61 | 9.53 | 100k | 15.1 |
| bus_gate_i | 0.49 | 0.91 | 0.43 | 0.62 | 0.60 | 10.80 | 100k | 16.3 |
| attnmem | 0.66 | 0.89 | 0.41 | 0.50 | 0.60 | 13.43 | 102k | 52.8 |
| bus_film_s | 0.50 | 0.93 | 0.43 | 0.59 | 0.60 | 8.70 | 100k | 21.1 |
| bus_add_i | 0.46 | 0.90 | 0.43 | 0.63 | 0.59 | 11.13 | 100k | 14.8 |
| vit | 0.39 | 0.94 | 0.43 | 0.64 | 0.59 | 11.80 | 96k | 184.3 |
| subbus_i | 0.44 | 0.87 | 0.42 | 0.63 | 0.58 | 13.03 | 99k | 22.3 |
| mlp | 0.45 | 0.90 | 0.35 | 0.56 | 0.56 | 13.30 | 100k | 10.3 |
| cvnn | 0.36 | 0.71 | 0.33 | 0.53 | 0.48 | 16.70 | 100k | 14.9 |

## Score je Task

![heatmap](heatmap.png)

| Modell | cycle | bitseq | cycle_mem | count | numseq | shapes | digits | charnext | paddle | paddle_mem | bricks | bricks_mem | crossing | racer | maze |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mlp | 0.48 | 0.76 | 0.01 | 0.97 | 0.04 | 0.93 | 0.87 | 0.35 | 1.00 | 0.76 | 1.00 | 0.57 | 0.03 | 0.25 | 0.30 |
| cnn | 0.56 | 0.77 | 0.00 | 1.00 | 0.87 | 1.00 | 0.97 | 0.38 | 1.00 | 0.85 | 1.00 | 0.61 | 0.77 | 0.53 | 0.72 |
| cvnn | 0.31 | 0.66 | 0.00 | 0.79 | 0.05 | 0.83 | 0.59 | 0.33 | 1.00 | 0.81 | 0.96 | 0.41 | 0.03 | 0.19 | 0.30 |
| vit | 0.27 | 0.67 | 0.00 | 1.00 | 0.03 | 0.98 | 0.90 | 0.43 | 0.99 | 0.87 | 0.96 | 0.45 | 0.14 | 0.48 | 0.61 |
| gru | 0.47 | 0.78 | 0.37 | 0.94 | 0.04 | 0.90 | 0.85 | 0.36 | 1.00 | 0.99 | 0.97 | 0.88 | 0.00 | 0.20 | 0.44 |
| attnmem | 0.52 | 0.71 | 1.00 | 1.00 | 0.05 | 0.92 | 0.87 | 0.41 | 0.98 | 0.93 | 0.49 | 0.50 | 0.01 | 0.22 | 0.40 |
| bus_add_s | 0.53 | 0.75 | 0.00 | 1.00 | 0.12 | 0.95 | 0.91 | 0.43 | 1.00 | 0.81 | 1.00 | 0.65 | 0.34 | 0.36 | 0.41 |
| bus_add_i | 0.50 | 0.70 | 0.00 | 0.99 | 0.08 | 0.90 | 0.90 | 0.43 | 1.00 | 0.90 | 1.00 | 0.67 | 0.10 | 0.32 | 0.41 |
| bus_mul_s | 0.62 | 0.75 | 0.00 | 1.00 | 0.23 | 0.95 | 0.93 | 0.43 | 1.00 | 0.82 | 1.00 | 0.76 | 0.20 | 0.30 | 0.42 |
| bus_mul_i | 0.56 | 0.77 | 0.00 | 1.00 | 0.12 | 0.93 | 0.90 | 0.42 | 1.00 | 0.89 | 0.97 | 0.74 | 0.14 | 0.31 | 0.41 |
| bus_gate_s | 0.55 | 0.77 | 0.00 | 1.00 | 0.13 | 0.94 | 0.91 | 0.43 | 1.00 | 0.80 | 1.00 | 0.76 | 0.27 | 0.36 | 0.40 |
| bus_gate_i | 0.54 | 0.75 | 0.00 | 1.00 | 0.15 | 0.91 | 0.91 | 0.43 | 1.00 | 0.82 | 0.99 | 0.59 | 0.22 | 0.35 | 0.39 |
| bus_film_s | 0.58 | 0.77 | 0.00 | 1.00 | 0.17 | 0.94 | 0.92 | 0.43 | 1.00 | 0.64 | 1.00 | 0.62 | 0.17 | 0.30 | 0.42 |
| bus_film_i | 0.55 | 0.77 | 0.00 | 1.00 | 0.13 | 0.92 | 0.91 | 0.44 | 1.00 | 0.79 | 1.00 | 0.76 | 0.10 | 0.33 | 0.42 |
| subbus_i | 0.47 | 0.69 | 0.00 | 0.99 | 0.03 | 0.87 | 0.88 | 0.42 | 1.00 | 0.84 | 0.98 | 0.65 | 0.15 | 0.32 | 0.46 |
| layer_s | 0.94 | 0.70 | 1.00 | 1.00 | 0.99 | 1.00 | 0.97 | 0.43 | 1.00 | 0.99 | 0.99 | 0.99 | 0.22 | 0.54 | 0.52 |
| layer_i | 0.78 | 0.70 | 0.89 | 1.00 | 0.65 | 0.97 | 0.94 | 0.44 | 1.00 | 1.00 | 0.93 | 0.84 | 0.06 | 0.38 | 0.46 |
| hier_s | 0.81 | 0.75 | 0.88 | 1.00 | 0.93 | 0.98 | 0.95 | 0.43 | 0.97 | 0.94 | 0.90 | 0.92 | 0.03 | 0.35 | 0.37 |
| hier_i | 0.64 | 0.75 | 0.10 | 1.00 | 0.26 | 0.95 | 0.92 | 0.41 | 0.96 | 0.98 | 0.82 | 0.84 | 0.01 | 0.29 | 0.39 |

## Rohmetriken je Task

### cycle

rows = time steps; repeating cycle of 2-8 words (8 bit), 2P..16 rows visible -> next row; test cycles held out

| Modell | acc | score |
|---|---|---|
| mlp | 0.48 | 0.48 |
| cnn | 0.56 | 0.56 |
| cvnn | 0.31 | 0.31 |
| vit | 0.27 | 0.27 |
| gru | 0.47 | 0.47 |
| attnmem | 0.52 | 0.52 |
| bus_add_s | 0.53 | 0.53 |
| bus_add_i | 0.50 | 0.50 |
| bus_mul_s | 0.62 | 0.62 |
| bus_mul_i | 0.56 | 0.56 |
| bus_gate_s | 0.55 | 0.55 |
| bus_gate_i | 0.54 | 0.54 |
| bus_film_s | 0.58 | 0.58 |
| bus_film_i | 0.55 | 0.55 |
| subbus_i | 0.47 | 0.47 |
| layer_s | 0.94 | 0.94 |
| layer_i | 0.78 | 0.78 |
| hier_s | 0.81 | 0.81 |
| hier_i | 0.64 | 0.64 |

### bitseq

mixed bit-stream generators (periodic, counter, growing runs, xor of cycles, LFSR), 16 bits visible -> next bit; test params held out

| Modell | acc | score |
|---|---|---|
| mlp | 0.88 | 0.76 |
| cnn | 0.88 | 0.77 |
| cvnn | 0.83 | 0.66 |
| vit | 0.84 | 0.67 |
| gru | 0.89 | 0.78 |
| attnmem | 0.85 | 0.71 |
| bus_add_s | 0.87 | 0.75 |
| bus_add_i | 0.85 | 0.70 |
| bus_mul_s | 0.88 | 0.75 |
| bus_mul_i | 0.89 | 0.77 |
| bus_gate_s | 0.89 | 0.77 |
| bus_gate_i | 0.87 | 0.75 |
| bus_film_s | 0.88 | 0.77 |
| bus_film_i | 0.88 | 0.77 |
| subbus_i | 0.84 | 0.69 |
| layer_s | 0.85 | 0.70 |
| layer_i | 0.85 | 0.70 |
| hier_s | 0.88 | 0.75 |
| hier_i | 0.87 | 0.75 |

### cycle_mem

repeating cycle of 2-8 words, only the current row visible -> next row (needs memory)

| Modell | acc | score |
|---|---|---|
| mlp | 0.01 | 0.01 |
| cnn | 0.00 | 0.00 |
| cvnn | 0.00 | 0.00 |
| vit | 0.00 | 0.00 |
| gru | 0.37 | 0.37 |
| attnmem | 1.00 | 1.00 |
| bus_add_s | 0.00 | 0.00 |
| bus_add_i | 0.00 | 0.00 |
| bus_mul_s | 0.00 | 0.00 |
| bus_mul_i | 0.00 | 0.00 |
| bus_gate_s | 0.00 | 0.00 |
| bus_gate_i | 0.00 | 0.00 |
| bus_film_s | 0.00 | 0.00 |
| bus_film_i | 0.00 | 0.00 |
| subbus_i | 0.00 | 0.00 |
| layer_s | 1.00 | 1.00 |
| layer_i | 0.89 | 0.89 |
| hier_s | 0.88 | 0.88 |
| hier_i | 0.10 | 0.10 |

### count

rows = counter v, v+1, ... (random start), 2-16 rows visible -> next

| Modell | acc | score |
|---|---|---|
| mlp | 0.97 | 0.97 |
| cnn | 1.00 | 1.00 |
| cvnn | 0.79 | 0.79 |
| vit | 1.00 | 1.00 |
| gru | 0.94 | 0.94 |
| attnmem | 1.00 | 1.00 |
| bus_add_s | 1.00 | 1.00 |
| bus_add_i | 0.99 | 0.99 |
| bus_mul_s | 1.00 | 1.00 |
| bus_mul_i | 1.00 | 1.00 |
| bus_gate_s | 1.00 | 1.00 |
| bus_gate_i | 1.00 | 1.00 |
| bus_film_s | 1.00 | 1.00 |
| bus_film_i | 1.00 | 1.00 |
| subbus_i | 0.99 | 0.99 |
| layer_s | 1.00 | 1.00 |
| layer_i | 1.00 | 1.00 |
| hier_s | 1.00 | 1.00 |
| hier_i | 1.00 | 1.00 |

### numseq

3 rows, rule arithmetic (k=1..63) or fibonacci-like -> next number

| Modell | acc | score |
|---|---|---|
| mlp | 0.04 | 0.04 |
| cnn | 0.87 | 0.87 |
| cvnn | 0.05 | 0.05 |
| vit | 0.03 | 0.03 |
| gru | 0.04 | 0.04 |
| attnmem | 0.05 | 0.05 |
| bus_add_s | 0.12 | 0.12 |
| bus_add_i | 0.08 | 0.08 |
| bus_mul_s | 0.23 | 0.23 |
| bus_mul_i | 0.12 | 0.12 |
| bus_gate_s | 0.13 | 0.13 |
| bus_gate_i | 0.15 | 0.15 |
| bus_film_s | 0.17 | 0.17 |
| bus_film_i | 0.13 | 0.13 |
| subbus_i | 0.03 | 0.03 |
| layer_s | 0.99 | 0.99 |
| layer_i | 0.65 | 0.65 |
| hier_s | 0.93 | 0.93 |
| hier_i | 0.26 | 0.26 |

### shapes

6 geometric shapes, random size/pos/colour, 2% pixel noise

| Modell | acc | score |
|---|---|---|
| mlp | 0.95 | 0.93 |
| cnn | 1.00 | 1.00 |
| cvnn | 0.86 | 0.83 |
| vit | 0.98 | 0.98 |
| gru | 0.92 | 0.90 |
| attnmem | 0.93 | 0.92 |
| bus_add_s | 0.96 | 0.95 |
| bus_add_i | 0.92 | 0.90 |
| bus_mul_s | 0.96 | 0.95 |
| bus_mul_i | 0.94 | 0.93 |
| bus_gate_s | 0.95 | 0.94 |
| bus_gate_i | 0.93 | 0.91 |
| bus_film_s | 0.95 | 0.94 |
| bus_film_i | 0.93 | 0.92 |
| subbus_i | 0.89 | 0.87 |
| layer_s | 1.00 | 1.00 |
| layer_i | 0.97 | 0.97 |
| hier_s | 0.98 | 0.98 |
| hier_i | 0.96 | 0.95 |

### digits

digit OCR from system fonts; test fonts held out

| Modell | acc | score |
|---|---|---|
| mlp | 0.88 | 0.87 |
| cnn | 0.97 | 0.97 |
| cvnn | 0.63 | 0.59 |
| vit | 0.91 | 0.90 |
| gru | 0.87 | 0.85 |
| attnmem | 0.88 | 0.87 |
| bus_add_s | 0.92 | 0.91 |
| bus_add_i | 0.91 | 0.90 |
| bus_mul_s | 0.93 | 0.93 |
| bus_mul_i | 0.91 | 0.90 |
| bus_gate_s | 0.92 | 0.91 |
| bus_gate_i | 0.92 | 0.91 |
| bus_film_s | 0.93 | 0.92 |
| bus_film_i | 0.92 | 0.91 |
| subbus_i | 0.89 | 0.88 |
| layer_s | 0.97 | 0.97 |
| layer_i | 0.95 | 0.94 |
| hier_s | 0.96 | 0.95 |
| hier_i | 0.92 | 0.92 |

### charnext

next char; last 16 chars as one-hot rows (col=i%16, ch=i//16)

| Modell | acc | bpc | score |
|---|---|---|---|
| mlp | 0.47 | 2.62 | 0.35 |
| cnn | 0.50 | 2.53 | 0.38 |
| cvnn | 0.46 | 2.73 | 0.33 |
| vit | 0.54 | 2.24 | 0.43 |
| gru | 0.48 | 2.56 | 0.36 |
| attnmem | 0.52 | 2.36 | 0.41 |
| bus_add_s | 0.53 | 2.32 | 0.43 |
| bus_add_i | 0.53 | 2.32 | 0.43 |
| bus_mul_s | 0.53 | 2.35 | 0.43 |
| bus_mul_i | 0.52 | 2.35 | 0.42 |
| bus_gate_s | 0.54 | 2.33 | 0.43 |
| bus_gate_i | 0.54 | 2.27 | 0.43 |
| bus_film_s | 0.54 | 2.30 | 0.43 |
| bus_film_i | 0.54 | 2.27 | 0.44 |
| subbus_i | 0.53 | 2.33 | 0.42 |
| layer_s | 0.54 | 2.30 | 0.43 |
| layer_i | 0.54 | 2.26 | 0.44 |
| hier_s | 0.54 | 2.29 | 0.43 |
| hier_i | 0.52 | 2.35 | 0.41 |

### paddle (Random: -2.03, Experte: 4.88)

paddle duel vs CPU, first to 5 points

| Modell | return | ep_len | score |
|---|---|---|---|
| mlp | 4.88 | 110.88 | 1.00 |
| cnn | 4.88 | 110.88 | 1.00 |
| cvnn | 4.88 | 110.88 | 1.00 |
| vit | 4.81 | 113.00 | 0.99 |
| gru | 4.88 | 110.88 | 1.00 |
| attnmem | 4.72 | 104.81 | 0.98 |
| bus_add_s | 4.88 | 110.88 | 1.00 |
| bus_add_i | 4.88 | 110.88 | 1.00 |
| bus_mul_s | 4.88 | 110.88 | 1.00 |
| bus_mul_i | 4.88 | 110.88 | 1.00 |
| bus_gate_s | 4.88 | 110.88 | 1.00 |
| bus_gate_i | 4.88 | 110.88 | 1.00 |
| bus_film_s | 4.88 | 110.88 | 1.00 |
| bus_film_i | 4.88 | 110.88 | 1.00 |
| subbus_i | 4.88 | 110.88 | 1.00 |
| layer_s | 4.88 | 110.88 | 1.00 |
| layer_i | 4.84 | 108.69 | 1.00 |
| hier_s | 4.66 | 108.78 | 0.97 |
| hier_i | 4.62 | 112.88 | 0.96 |

### paddle_mem (Random: -2.03, Experte: 4.88)

paddle duel without ball trail (needs memory)

| Modell | return | ep_len | score |
|---|---|---|---|
| mlp | 3.22 | 105.81 | 0.76 |
| cnn | 3.84 | 102.00 | 0.85 |
| cvnn | 3.53 | 97.16 | 0.81 |
| vit | 3.97 | 105.12 | 0.87 |
| gru | 4.81 | 113.81 | 0.99 |
| attnmem | 4.38 | 103.03 | 0.93 |
| bus_add_s | 3.53 | 114.34 | 0.81 |
| bus_add_i | 4.19 | 109.88 | 0.90 |
| bus_mul_s | 3.62 | 103.97 | 0.82 |
| bus_mul_i | 4.12 | 114.44 | 0.89 |
| bus_gate_s | 3.47 | 116.38 | 0.80 |
| bus_gate_i | 3.66 | 115.09 | 0.82 |
| bus_film_s | 2.41 | 96.69 | 0.64 |
| bus_film_i | 3.44 | 106.72 | 0.79 |
| subbus_i | 3.78 | 103.41 | 0.84 |
| layer_s | 4.78 | 106.75 | 0.99 |
| layer_i | 4.84 | 109.50 | 1.00 |
| hier_s | 4.47 | 109.28 | 0.94 |
| hier_i | 4.72 | 111.31 | 0.98 |

### bricks (Random: 0.62, Experte: 51.22)

clear 64 bricks, 3 lives

| Modell | return | ep_len | score |
|---|---|---|---|
| mlp | 51.47 | 600.00 | 1.00 |
| cnn | 51.12 | 598.53 | 1.00 |
| cvnn | 49.34 | 570.16 | 0.96 |
| vit | 49.38 | 581.72 | 0.96 |
| gru | 49.72 | 580.31 | 0.97 |
| attnmem | 25.38 | 411.19 | 0.49 |
| bus_add_s | 51.09 | 600.00 | 1.00 |
| bus_add_i | 51.22 | 600.00 | 1.00 |
| bus_mul_s | 51.22 | 600.00 | 1.00 |
| bus_mul_i | 49.84 | 597.84 | 0.97 |
| bus_gate_s | 51.22 | 600.00 | 1.00 |
| bus_gate_i | 50.66 | 600.00 | 0.99 |
| bus_film_s | 51.16 | 600.00 | 1.00 |
| bus_film_i | 51.09 | 600.00 | 1.00 |
| subbus_i | 50.31 | 596.66 | 0.98 |
| layer_s | 50.56 | 592.66 | 0.99 |
| layer_i | 47.78 | 561.16 | 0.93 |
| hier_s | 46.28 | 559.28 | 0.90 |
| hier_i | 42.22 | 499.62 | 0.82 |

### bricks_mem (Random: 0.62, Experte: 51.22)

bricks without ball trail (needs memory)

| Modell | return | ep_len | score |
|---|---|---|---|
| mlp | 29.31 | 432.09 | 0.57 |
| cnn | 31.59 | 427.00 | 0.61 |
| cvnn | 21.16 | 354.50 | 0.41 |
| vit | 23.41 | 334.31 | 0.45 |
| gru | 45.28 | 536.75 | 0.88 |
| attnmem | 25.75 | 354.56 | 0.50 |
| bus_add_s | 33.66 | 438.34 | 0.65 |
| bus_add_i | 34.56 | 435.38 | 0.67 |
| bus_mul_s | 39.25 | 496.25 | 0.76 |
| bus_mul_i | 38.25 | 488.50 | 0.74 |
| bus_gate_s | 38.84 | 471.53 | 0.76 |
| bus_gate_i | 30.28 | 427.34 | 0.59 |
| bus_film_s | 32.22 | 404.03 | 0.62 |
| bus_film_i | 39.28 | 508.00 | 0.76 |
| subbus_i | 33.31 | 436.69 | 0.65 |
| layer_s | 50.75 | 600.00 | 0.99 |
| layer_i | 43.34 | 519.56 | 0.84 |
| hier_s | 47.22 | 570.50 | 0.92 |
| hier_i | 42.88 | 511.28 | 0.84 |

### crossing (Random: -1.00, Experte: 11.22)

cross 10 traffic lanes, +1 per crossing

| Modell | return | ep_len | score |
|---|---|---|---|
| mlp | -0.66 | 22.81 | 0.03 |
| cnn | 8.38 | 232.19 | 0.77 |
| cvnn | -0.66 | 21.47 | 0.03 |
| vit | 0.69 | 55.66 | 0.14 |
| gru | -0.97 | 13.28 | 0.00 |
| attnmem | -0.91 | 18.06 | 0.01 |
| bus_add_s | 3.16 | 107.19 | 0.34 |
| bus_add_i | 0.25 | 46.62 | 0.10 |
| bus_mul_s | 1.44 | 73.28 | 0.20 |
| bus_mul_i | 0.72 | 55.47 | 0.14 |
| bus_gate_s | 2.34 | 88.59 | 0.27 |
| bus_gate_i | 1.69 | 81.00 | 0.22 |
| bus_film_s | 1.12 | 65.09 | 0.17 |
| bus_film_i | 0.22 | 46.31 | 0.10 |
| subbus_i | 0.88 | 55.88 | 0.15 |
| layer_s | 1.66 | 71.22 | 0.22 |
| layer_i | -0.31 | 24.78 | 0.06 |
| hier_s | -0.62 | 22.84 | 0.03 |
| hier_i | -0.94 | 14.81 | 0.01 |

### racer (Random: 19.66, Experte: 280.91)

dodge obstacles, +1 per step survived

| Modell | return | ep_len | score |
|---|---|---|---|
| mlp | 83.78 | 84.75 | 0.25 |
| cnn | 158.31 | 159.16 | 0.53 |
| cvnn | 68.81 | 69.81 | 0.19 |
| vit | 145.47 | 146.34 | 0.48 |
| gru | 70.97 | 71.97 | 0.20 |
| attnmem | 76.00 | 77.00 | 0.22 |
| bus_add_s | 114.12 | 115.06 | 0.36 |
| bus_add_i | 103.75 | 104.72 | 0.32 |
| bus_mul_s | 99.12 | 100.09 | 0.30 |
| bus_mul_i | 100.91 | 101.91 | 0.31 |
| bus_gate_s | 113.06 | 114.03 | 0.36 |
| bus_gate_i | 110.47 | 111.41 | 0.35 |
| bus_film_s | 98.09 | 99.09 | 0.30 |
| bus_film_i | 105.41 | 106.38 | 0.33 |
| subbus_i | 104.44 | 105.41 | 0.32 |
| layer_s | 161.56 | 162.34 | 0.54 |
| layer_i | 118.97 | 119.94 | 0.38 |
| hier_s | 111.88 | 112.84 | 0.35 |
| hier_i | 96.12 | 97.06 | 0.29 |

### maze (Random: -0.81, Experte: 36.72)

collect pellets, avoid 2 chasers

| Modell | return | ep_len | score |
|---|---|---|---|
| mlp | 10.59 | 31.72 | 0.30 |
| cnn | 26.03 | 49.72 | 0.72 |
| cvnn | 10.59 | 31.66 | 0.30 |
| vit | 21.94 | 45.28 | 0.61 |
| gru | 15.78 | 34.75 | 0.44 |
| attnmem | 14.12 | 32.97 | 0.40 |
| bus_add_s | 14.75 | 34.66 | 0.41 |
| bus_add_i | 14.62 | 34.97 | 0.41 |
| bus_mul_s | 15.09 | 35.22 | 0.42 |
| bus_mul_i | 14.69 | 33.88 | 0.41 |
| bus_gate_s | 14.38 | 35.19 | 0.40 |
| bus_gate_i | 13.84 | 33.88 | 0.39 |
| bus_film_s | 14.97 | 34.25 | 0.42 |
| bus_film_i | 14.97 | 35.00 | 0.42 |
| subbus_i | 16.56 | 38.06 | 0.46 |
| layer_s | 18.62 | 36.91 | 0.52 |
| layer_i | 16.34 | 35.09 | 0.46 |
| hier_s | 12.97 | 29.22 | 0.37 |
| hier_i | 14.00 | 33.31 | 0.39 |
