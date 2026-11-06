# NetResearch

Ziel ist es eine Platform mit verschiedenen Test-Szenarios für das Training uns die vergleichende Prüfung verschiedener Architekturen von Neuronalen-Netzen aufzubauen.
Die Inputs und Outputs sollen zwischen den Szenarios möglichst einheitlich sein um Netze ohne große Anpassungen austauschen zu können.
Es wird also ein "größter gemeinsamer Nenner" gesucht, soweit möglich. Gänzlich Einheitlich wird es zwischen verschiedenen Test-Klassen nicht zu machen sein.

## Ideen für Test-Szenarios:

Video-Games:
* Frogger
* Breakout
* Ping-Pong
* Pinball
* Pac-Man
* Race
* ...

Patterns:
* Bitmuster erkennen und fortsetzen (Count, Repeating-Cycles, ...)
* ...

Image:
* Klassifizierung (geometrische Figuren, ...) 
* OCR (Numbers)
* ...

Text:
* next char in text
* ...

## Architektur

### Input & Output

Idee für einheitlichen Input:
* 8x8 (oder 16x16) Raster für Image Input, RGB (0/1)

Idee für einheitlichen Output:
* left, right, up, down
* Button Fire, Jump, ...

## Funktionen
Funktionen die die untersuchten Netze (Optional) haben sollen.
* Training (Back-Prop, White-Space programming/editing durch LLM, ...)
* Memory
* Attention
* Komplexe-Werte
* ...

## Architekturen

### Ein großes Netz
* NN (klassisch)
* CNN oder ConvNet (Convolutional Neural Network)
* CVNN (Complex-Valued Neural Network)
* ...

### Modulares Netz
Jeweils den Ansatz überprüfen: Individuelle Module und ein einheitlich trainiertes Modul an jeder Stelle.

* Hierarchisch
* Layer
* Bus
* Bus/ Sub-Bus


### Hierarchische Netz-Module
Die Idee der hierarchischen Netz-Module habe ich schon ein wenig ausgearbeitet.

```
  Input

 .-----.
 |     |
 `-----´

             .-----.
             | P   |
             `-----´
             
 .-----.                 .-----.
 | LP  |                 | RP  |
 `-----´                 `-----´
 
             .-----.                 .-----.
             |  X  |                 |     | ...
             `-----´                 `-----´

 .-----.                 .-----.
 | LS  |                 | RS  | ...
 `-----´                 `-----´
 
             .-----.
             | S   | ...
             `-----´

 .-----.
 |     | ...
 `-----´
 
 ...
 
  Output
```

"X" ist das beschriebene Modul.
"P" ist das "Parent", "LP" ist der "Left-Parent", "RP" ist der "Right-Parent".
"S" ist das "Sibling", "LS" ist der "Left-Sibling", "RS" ist der "Right-Sibling".
An den Rändern der Hierarchie werden Inputs und Outputs nicht genutzt.
Die Hierarchie kann in der Tiefe und damit dann auch der Breite beliebig vergößert werden.

Modul ("I.." ist "Input" des Moduls "X" von dem angegeben Modul, "O.." ist Output des Moduls "X" zu dem angegeben Modul):
```
    |     |     |     |
 .--V--+--V--+--V--+--V--.
 | ILS | ILP | IP  | IRP |
 |-----+-----+-----+-----+
 |                       |
 |-----+-----+-----+-----+
 | OLS | OS  | ORS | ORP |
 `--V--+--V--+--V--+--V--´
    |     |     |     |
```

### Layer Netz-Module

```
  Input
  
  ...

 .-----.    .-----.    .-----.    .-----.
 | LP  |    | P   |    | RP  |    |     | ...
 `-----´    `-----´    `-----´    `-----´
 
 .-----.    .-----.    .-----.    .-----.
 | L   |    |  X  |    | R   |    |     | ...
 `-----´    `-----´    `-----´    `-----´

 .-----.    .-----.    .-----.    .-----.
 | LS  |    | S   |    | RS  |    |     | ...
 `-----´    `-----´    `-----´    `-----´
 
 ...

  Output
```

### Bus Netz-Module

```
  Input
  |
  |    ...
  |
  +-------.
  |       |
  |    .--V--.
  |    | X   |
  |    `--V--´
  |       |
  A<------´
  |    
  |    ...
  V
  Output
```

Im Einspeisepunkt "A" werden die Signale von Modul "X" mit den von oben kommenden Bus-Signalen verknüpft.
1. Rein Additiv (Der "Residual Stream" / Delta-Ansatz): $$B_{t+1} = B_t + f_i(B_t)$$
2. Rein Multiplikativ (Modulation / Filterung): $$B_{t+1} = B_t \odot f_i(B_t)$$
3. Gated Addition / Konvexe Kombination (Highway- / GRU-Prinzip): $$B_{t+1} = (1 - G_i) \odot B_t + G_i \odot f_i(B_t)$$
4. Feature-wise Linear Modulation (FiLM – Kombiniert): $$B_{t+1} = \gamma_i(B_t) \odot B_t + \beta_i(B_t)$$

Ein Modul könnte aus mehreren Sub-Modulen bestehen die intern wieder an einem gemeinsamen Input/Output-Bus hängen.
