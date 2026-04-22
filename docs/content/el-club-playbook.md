# El Club · Playbook (Knowledge File)
**Para:** Custom GPT "El Club · Creative Director"
**Última actualización:** 2026-04-22
**Uso:** El GPT debe consultar este archivo ANTES de generar cualquier imagen. Contiene specs completas de cada command mode, las 9 historias del catálogo, prompts canonical para anchor images, y ejemplos de iteración.

---

## Índice de modes

- [Product Mode (default)](#product-mode)
- [Back view](#back-view)
- [Detail Mode](#detail-mode)
- [Player Mode](#player-mode)
- [Post Mode](#post-mode)
- [Ad Mode](#ad-mode)
- [Vault Mode](#vault-mode)
- [Reel Storyboard Mode](#reel-storyboard-mode)
- [Historia Mode](#historia-mode)
- [Batch Mode](#batch-mode)
- [Anchor generation prompts](#anchor-generation-prompts)
- [Las 9 historias del catálogo](#las-9-historias-del-catalogo)
- [Pricing + productos](#pricing)
- [Troubleshooting común](#troubleshooting)

---

## Product Mode

**Trigger:** default · `producto [equipo] [temporada]` · `producto [jersey name]`

### Specs

**Layout:** Flat lay, camera 90° overhead (bird's eye).

**Jersey state:**
- Neatly laid flat
- Sleeves angled ~20° outward from body (shows full silhouette)
- Collar visible and clean, pointing up
- No wrinkles, no folds, no hanger, no mannequin, no person
- Subtle natural fabric texture visible (real-cloth feel, not CGI)

**Orientation:**
- Jersey centered
- Front facing up (unless `back` command)
- Slight natural fabric texture — NOT digital smooth

**Framing:**
- Jersey occupies ~70% of frame
- Generous padding on all sides
- Aspect: 1:1 (1080×1080px)

### Lighting recipe
- Key: upper-left 10 o'clock, warm 2800-3200K
- Fill: right side, neutral, ~30% intensity
- Subtle matte reflection beneath jersey (grounds it — jersey should NOT look floating)
- Rim light catches edges of sleeves and collar

### Reference
Always apply `brand-anchor-flatlay.png` style.

### Example prompt (Inter Milan 09/10 away)

```
STYLE ANCHOR: Match exact lighting, background gradient, color grading,
and contrast of brand-anchor-flatlay.png.

SCENE: Pure black-to-charcoal gradient (#0D0D0D edges, #1C1C1C center),
smooth organic falloff, no hard vignette.

SUBJECT: Single Inter Milan 2009/2010 away football jersey laid flat.
White body with navy blue and black vertical stripes on the sides,
Pirelli sponsor in navy block letters on chest, Nike swoosh navy on
upper right chest, Inter Milan crest embroidered on upper left chest
(gold and blue). Sleeves angled 20° outward, collar clean at top.

DETAILS: Late-2000s polyester weave texture visible. Embroidered crest
(not printed). Period-accurate short sleeves. Natural subtle folds.
Small tri-color band (Italian flag) at back neck if visible.

LIGHTING: Key light upper-left 2800K warm. Fill right 30% neutral.
Subtle matte reflection beneath jersey. Rim light on sleeve edges.
Deep shadows at edges, readable exposure throughout.

COMPOSITION: Bird's eye 90° overhead. 1:1 square 1080×1080.
Jersey 70% of frame, equal padding all sides, perfectly centered.

CONSTRAINTS: Photorealistic editorial product photography.
Only the jersey has color (white + navy + black + sponsor colors).
Background strictly Midnight Stadium palette. No watermark,
no text on image, no extra graphics. Quality: high.
```

---

## Back view

**Trigger:** `back` (after a product shot) · `producto [jersey] back`

### Specs

Same as Product Mode but jersey flipped to show back:
- Back print visible (name + number if specified)
- Back neck label (single tag, clean, no size visible)
- Back of sponsor's printing (if shows through)

### Text rendering on back

If user specifies name + number:
- Use Text Rendering Protocol
- Specify exact name spelling letter-by-letter
- Specify number digit count
- Number font: typical football jersey font (bold, stylized)
- Placement: large number centered vertically, name in arc above

### Example prompt (Argentina 1986 away back · MESSI 10)

```
STYLE ANCHOR: Match brand-anchor-flatlay.png.

SCENE: Pure black-to-charcoal gradient.

SUBJECT: Argentina 1986 away jersey, BACK view, laid flat. Light blue
body, white stripes vertical. Retro Le Coq Sportif style collar seen
from back.

DETAILS: Period-accurate fabric weave. Vintage hand-stitched feel.

LIGHTING: Same as Product Mode anchor.

COMPOSITION: Flat lay 90° overhead, 1:1 square, 70% of frame.

TEXT: Add "MESSI" spelled M-E-S-S-I in bold football-jersey font,
white color #FFFFFF, in an arc shape above a large number "10"
(digit one and zero). Font style: period-accurate 1980s football
lettering, white printed look. Number "10" centered horizontally,
occupying ~20% of jersey height, positioned in the upper-middle back
area. EXACT spelling, no misspellings.

CONSTRAINTS: Photorealistic. Only jersey colored. No watermark.
Quality: high.
```

---

## Detail Mode

**Trigger:** `detail [zone]`

### Core principle
Show the detail ON the jersey, not detached from it. Detail is the star; surrounding jersey provides the stage.

### Framing
- Camera angle: slight 15-30° from flat (reveals texture depth and stitching dimensionality)
- Focus zone: specified detail occupies 40-50% of frame, sharp and crisp
- Surrounding jersey fills remaining frame in gradually softer focus (shallow DOF)
- Jersey must bleed off-frame on at least one side
- Always include one landmark near the detail:

| Detail zone | Landmark required nearby |
|-------------|--------------------------|
| badge | collar OR sponsor |
| collar | top of badge OR shoulder seam |
| sleeve | shoulder seam AND part of body |
| sponsor | badge on one side |
| back print | collar and shoulder area |
| texture | visible stitching/seam for scale |
| patch | adjacent badge or sponsor |

### Lighting
- Slightly raked/side lighting to emphasize texture
- Key light from ~8 o'clock position (shallow angle → longer micro-shadows)
- Fabric MUST look unmistakably real
- Show thread count, weave pattern, how printed logos sit differently than embroidered ones

### Aspect
1:1 (1080×1080px)

### Example prompt (`detail badge` — Real Madrid crest)

```
STYLE ANCHOR: Match brand-anchor-flatlay.png mood + lighting, but
adjust angle to 20° raked (not pure overhead).

SCENE: Pure black-to-charcoal gradient.

SUBJECT: Extreme close-up of the Real Madrid embroidered crest on a
white Real Madrid 26/27 home jersey. Royal crown, "R" and "M" letters
intertwined, gold and blue thread. Crest occupies 45% of frame.
Visible: part of white collar (top-right of crest) and a sliver of
upper chest white fabric (below crest) to anchor context.

DETAILS: Embroidered texture clearly visible — individual gold and
blue thread passes, slight 3D depth, micro-shadows between threads.
Fabric beneath crest shows fine mesh weave (modern Adidas aero-style).

LIGHTING: Key light from 8 o'clock position, slightly raked side.
Emphasizes thread texture through long micro-shadows. Highlights on
gold thread strands.

COMPOSITION: 20° raked angle (not flat overhead). 1:1 square.
Shallow depth of field — crest fully sharp, surrounding jersey
gradually softer.

CONSTRAINTS: Photorealistic macro product photography. Only the crest
area and adjacent jersey have color. No watermark, no text.
Quality: high.
```

---

## Player Mode

**Trigger:** `player [name]` · `player [jersey description]`

### Core principle
**The jersey is protagonist. The player is vessel.** Every compositional choice exists to showcase the jersey. Eye lands on fabric first.

### Composition
- Waist-up or chest-up portrait
- Camera slightly below eye level (low angle, heroic)
- Frame so JERSEY occupies the largest area
- Chest/torso = focal center, NOT face

### Background
- Dark stadium atmosphere — felt, not seen
- NEVER a recognizable real stadium
- Blurred deep blacks + dark blues (#1C2A3A for cool fill)
- Subtle bokeh of distant stadium lights
- Atmospheric fog/haze wraps around player silhouette BUT leaves jersey front clear

### Lighting recipe (Rembrandt style)
- **Key light:** upper-left, Rembrandt-style (creates characteristic triangle of light on shadow side of cheek below eye)
- **Rim light:** strong on opposite shoulder/hair to separate player from background
- **Fill:** subtle cool #1C2A3A to keep shadow detail
- **CRITICAL:** the BRIGHTEST, SHARPEST light falls on the JERSEY. Sponsor, badge, crest, fabric texture must be clearly lit and fully readable. The face can fall into partial shadow.

### Focus
- Sharp focus on jersey fabric + details
- Player's face can be slightly softer (shallow DOF)
- Player's face can be partially in shadow

### Player portrayal
- Serious, contemplative, iconic
- Looking slightly off-camera (3/4 gaze) OR straight ahead with quiet intensity
- NO smiling, NO action poses, NO celebrating, NO screaming
- Pre-match focus energy
- Chest slightly forward, shoulders square

### Atmospheric detail
Subtle atmospheric haze/fog between player and background. Haze wraps around player silhouette but leaves the jersey front CLEAR for readability.

### Color grading
- Teal-and-orange cinema grade, skewed dark
- Skin tones warm (not orange)
- Jersey colors remain 100% accurate despite grading (if green jersey, stays green; if blue, stays blue)

### Reference handling
- **If player reference provided:** match the player's likeness, build, and hair faithfully
- **If jersey-only reference:** generate generic athletic male mid-20s, fit build, face slightly obscured by shadow or angle (do NOT invent specific recognizable face)
- **If "player [name]":** generate the named player with faithful likeness; jersey must match reference perfectly

### Aspect
4:5 (1080×1350px) — optimized for IG feed and ads. Pushed more cinematic than default: deeper blacks, stronger contrast, stronger vignette.

### Example prompt (`player messi` with Argentina 2026)

```
STYLE ANCHOR: Match brand-anchor-player.png.

SCENE: Dark stadium haze — blurred blacks and dark blues (#0D0D0D
with hints of #1C2A3A), subtle bokeh of distant stadium floodlights,
atmospheric fog. Not a recognizable real stadium.

SUBJECT: Lionel Messi, age 38, faithful likeness: medium-length dark
hair, trimmed beard, known facial structure. Wearing Argentina 2026
home jersey — sky blue and white vertical stripes, three stars above
AFA crest, Adidas three stripes. Chest-up framing, camera slightly
below eye level.

DETAILS: Jersey shows modern Adidas weave, embroidered AFA crest,
three stars above crest, Adidas stripes on shoulders. Number "10"
visible partially (back, slight turn).

LIGHTING: Rembrandt key light upper-left creating light triangle on
face below right eye. Strong rim light on left shoulder/hair.
Subtle cool fill #1C2A3A on shadow side. BRIGHTEST LIGHT FALLS ON
JERSEY — chest/torso fully readable, crest and stripes clearly lit.
Face partially in shadow.

COMPOSITION: 4:5 portrait 1080×1350. Chest-up. Messi centered but
jersey/torso is largest area of image. Slight low angle (heroic).
Serious contemplative gaze 3/4 off-camera. No smile. Pre-match energy.

CONSTRAINTS: Photorealistic editorial cinematic portrait. Teal-and-
orange grade skewed dark. Jersey colors 100% accurate (sky blue and
white exact). Skin warm not orange. No smiling. No action pose.
No recognizable stadium. No watermark. Quality: high.
```

---

## Post Mode

**Trigger:** `post [type]`

### Core principle
Every post is a frame from the same film. The feed must feel like scrolling through a dark cinematic lookbook. Consistency in color, typography, and mood is non-negotiable.

### Typography rules
- **Headlines:** Oswald 700 uppercase, tight tracking, ≤6-8 words
- **Body:** Space Grotesk 400-500, ≤2 lines
- **Primary text color:** white #FFFFFF
- **Accent + CTA color:** Ice blue #4DA8FF
- **No other text colors allowed**

### Brand mark
El Club logo (small, bottom-right OR bottom-center) on every post.

### CTAs (rotate)
- "Pedí tu box →"
- "Link en bio"
- "DM para pedir"
- "Explorá el vault →"
- "Escribinos →"

### Taglines (rotate)
- "La camiseta te elige a vos."
- "No elegís. Descubrís."
- "Confiá en la caja."
- "Cada box tiene un destino."
- "Entrás al Club o te quedás afuera."

### Post types

| Command | Format | Description |
|---------|--------|-------------|
| `post comeback` | 1:1 | "Estamos de vuelta" dramatic announcement |
| `post reveal` | 1:1 | Product or launch reveal with overlay text |
| `post countdown [N]` | 1:1 | World Cup countdown, N huge and bold |
| `post poll "[question]"` | 9:16 | Poll graphic with space for IG sticker |
| `post bts` | 9:16 | Behind the scenes, moody atmospheric |
| `post quote` | 1:1 | Brand tagline, typography-driven |
| `post carousel "[title]"` | 1:1 | Cover slide with "deslizá →" |
| `post story` | 9:16 | Generic story template |
| `post reel "[title]"` | 9:16 | Reel cover thumbnail |
| `post historia [jersey]` | 1:1 | Storytelling using 9 historias |

### Example prompt (`post reveal` for vault launch)

```
STYLE ANCHOR: Match brand-anchor-hero.png.

SCENE: Pure black void (#0D0D0D) with subtle gradient toward #1C1C1C
at center. Dark wooden archive cabinet with glass doors visible in
center-left, containing multiple jerseys as silhouettes.

SUBJECT: One central jersey inside the cabinet is highlighted by a
warm spotlight — vibrant red retro-style football jersey visible
through the glass, catching light dramatically.

DETAILS: Cabinet has brass hinges and handles, vintage dark wood.
Jerseys inside on wooden hangers. Only the spotlighted jersey shows
vibrant color.

LIGHTING: Warm spotlight on central jersey. Cabinet edges catch faint
rim light. Everything else in atmospheric shadow. Readable exposure.

COMPOSITION: 1:1 square 1080×1080. Cabinet fills 75% of frame,
centered. Jersey on rule-of-thirds right.

TEXT:
- Line 1: "EL ARCHIVO ABRIÓ" spelled E-L A-R-C-H-I-V-O A-B-R-I-Ó,
  in Oswald 700 uppercase, white #FFFFFF, positioned across top third.
  Include accent mark over Ó.
- Line 2: "VAULT · ELCLUB.CLUB" in Space Grotesk 500, ice blue
  #4DA8FF, centered below Line 1, smaller size.
- EL CLUB logo small, bottom-right, white version.

CONSTRAINTS: Photorealistic editorial. EXACT text, no misspellings.
No additional graphics or watermarks. Quality: high.
```

---

## Ad Mode

**Trigger:** `ad [type]`

### Core principle
**Ads interrupt. Posts invite.** An ad has 0.3 seconds to justify itself. Bold visuals, clear value prop, minimal text. Every ad must pass the "thumb test."

### Quality standard
Highest tier. Must look agency-produced:
- Photorealism mandatory. If any element looks like a render → REGENERATE.
- Lighting cinematic, not flat.
- Composition intentional — every element placed with purpose.
- Text readable at phone size. If you have to zoom in, text is too small.

### Text rules
- **Primary headline:** Oswald 700 ALL CAPS white MASSIVE (first eye hit)
- **Price:** Oswald 700 white prominent (qualifies the viewer)
- **Strikethrough price (if applicable):** original smaller with strikethrough next to offer price
- **CTA:** Ice blue #4DA8FF — short: "Escribinos →", "Pedí la tuya →", "Explorá →"
- **Max 4-5 text elements total** — every word earns its place
- **Text NEVER covers the product** — use negative space or subtle dark overlays

### Ad types

| Command | Format | Description |
|---------|--------|-------------|
| `ad mystery` | 4:5 | Mystery Box ad — intrigue, glow, box as hero |
| `ad catalog` | 4:5 | Catalog ad — jersey hero, history, emotional |
| `ad vault` | 4:5 | Vault ad — archive cabinet drama |
| `ad demand` | 4:5 | On Demand — "any jersey you want" concept |
| `ad carousel` | 1:1 x N | Multi-slide (hook → reveal → CTA) |
| `ad story` | 9:16 | Story/Reel ad — vertical, bold |
| `ad morphing` | 4:5 | Multiple jerseys blending into one |
| `ad mundial` | 4:5 | WC2026 specific, countdown, selection hero |

### Composition techniques

**The Box Shot (`ad mystery`):**
- Real kraft cardboard box — texture visible, fiber imperfections, NOT smooth render
- Glow from inside: Ice blue #4DA8FF, subtle, NEVER neon
- Partial reveal: hint of jersey fabric peeking, never enough to identify team
- Must feel tangible — viewer should want to reach and open

**The Player Shot (`ad catalog`):**
- Player Mode specs pushed to maximum drama
- More contrast, more cinema
- Named players: match likeness faithfully
- Generic players: face obscured, athletic build, confident posture
- Jersey is ONLY thing in sharp focus

**The Morphing Shot (`ad morphing` / `ad demand`):**
- Single jersey transitioning between 2-3 reference jerseys
- Transitions flow diagonally across torso:
  - Left shoulder = Reference 1
  - Center chest = Reference 2
  - Right shoulder = Reference 3
- Transitions FLUID — smoke/particles/liquid-like blending in Ice blue #4DA8FF
- Each zone RECOGNIZABLE — badge and primary colors identifiable per section
- Can be flat lay OR on player wearing morphing jersey
- Communicates: "we can get you ANY of these"

**The Unboxing Sequence (`ad carousel`):**
- Slide 1: box closed, mystery, hook question
- Slide 2: box opening, hand interacting, anticipation
- Slide 3: jersey revealed, price visible, CTA
- Visual continuity: same lighting, surface, camera angle across all slides
- Each slide must compel swipe

### Example prompt (`ad mystery`)

```
STYLE ANCHOR: Match brand-anchor-hero.png with pushed drama
(deeper blacks, more contrast).

SCENE: Pure black void (#0D0D0D) with gradient lift at center
(#1C1C1C). Darker at edges.

SUBJECT: Closed kraft cardboard box, centered, three-quarter angle
showing top lid and one side. Box is real cardboard — visible fiber
texture, slight wear on one corner, matte finish. Small ice blue
#4DA8FF wax seal on lid. Subtle ice blue glow leaking from underneath
the lid edge (like the box has something magical inside).

DETAILS: Photorealistic kraft cardboard, not smooth render. Subtle
surface reflection beneath box.

LIGHTING: Dramatic spotlight from upper-left 2800K warm. Strong rim
light on right edge. Deep shadow behind and below box. The glow
from inside is the second light source.

COMPOSITION: 4:5 portrait 1080×1350. Box occupies 50% of frame,
centered vertically, slightly lower third. Negative space above
for text.

TEXT:
- Headline top: "MYSTERY BOX" in Oswald 700 uppercase white #FFFFFF,
  MASSIVE size, tight tracking.
- Below headline: "Q350" in Oswald 700 white, prominent.
- Small tag line below: "La camiseta te elige a vos." in Space
  Grotesk 400 white, smaller.
- CTA bottom-right: "Pedí la tuya →" in ice blue #4DA8FF,
  Space Grotesk 500.
- Logo bottom-left: EL CLUB (small, white).

CONSTRAINTS: Photorealistic. Agency-produced look. EXACT text.
No Canva feel. No watermark. Quality: high.
```

---

## Vault Mode

**Trigger:** `vault [sub-mode]`

### Core concept
Content specific to `vault.elclub.club` — the private archive of rare/unique jerseys. Visual key: wooden archive cabinet with glass doors, dark wood, brass hardware, against pure black void.

### Sub-modes

| Command | Format | Description |
|---------|--------|-------------|
| `vault hero` | 1:1 | Single cabinet, one jersey spotlighted |
| `vault overview` | 4:5 | Wider cabinet, multiple jerseys as silhouettes, one highlighted |
| `vault detail` | 1:1 | Close-up of hanger + jersey detail |
| `vault story` | 9:16 | Story format with "VAULT" badge overlay |

### Common specs
- Jerseys inside cabinet: mostly silhouettes in deep shadow
- One central jersey gets warm spotlight — ONLY vibrant color in frame
- Lighting: warm spotlight on subject. Cabinet edges faint rim. Everything else atmospheric shadow. Readable exposure.
- **Brand overlay:** "VAULT" badge in ice blue #4DA8FF, Oswald 700 uppercase, bottom-right corner.

### Example prompt (`vault hero` with Argentina 1986)

```
STYLE ANCHOR: Match brand-anchor-hero.png.

SCENE: Pure black void (#0D0D0D → #1C1C1C center). Dark wooden
archive cabinet with glass doors in center of frame, vintage
museum-grade, brass hinges and handles.

SUBJECT: Light blue vintage Argentina 1986 away jersey hanging inside
the cabinet on a wooden hanger, highlighted by warm spotlight.
Multiple other jerseys visible as silhouettes in deep shadow around
it. The Argentina jersey is the ONLY vibrant color in the entire
image (light blue + white stripes).

DETAILS: Cabinet dark wood grain visible. Brass hardware catches rim
light. Glass doors have subtle reflection of the spotlight. Argentina
jersey shows vintage cotton weave, hand-stitched crest appearance.

LIGHTING: Single warm spotlight on Argentina jersey. Cabinet edges
faint rim light. All other jerseys in atmospheric shadow.

COMPOSITION: 1:1 square 1080×1080. Cabinet fills 75% of frame
centered. Argentina jersey positioned on rule-of-thirds inside cabinet.

TEXT:
- Bottom-right corner: "VAULT" badge, Oswald 700 uppercase,
  ice blue #4DA8FF.
- Small EL CLUB logo bottom-left, white.

CONSTRAINTS: Photorealistic. No watermark. Quality: high.
```

---

## Reel Storyboard Mode

**Trigger:** `reel [concept]`

### Core concept
Generate a 5-image storyboard for Instagram Reels / TikTok. All 5 frames share identical lighting DNA, aspect ratio, and color grading. Reference same anchor across all 5.

### Aspect
9:16 (1080×1920px) per frame

### Output
One prompt per frame, numbered F1 through F5. Diego stitches them in CapCut/InShot with transitions.

### Standard structure

| Frame | Time | Role |
|-------|------|------|
| F1 | 0-3s | HOOK — visual attention grabber |
| F2 | 3-8s | BUILD — tension, pieces coming together |
| F3 | 8-14s | REVEAL — the thing the reel is about |
| F4 | 14-20s | CONTEXT — reveal in broader scene |
| F5 | 20-25s | CTA — text overlay + logo |

### Consistency protocol
Generate all 5 frames in the SAME chat session within the GPT. Reference anchor_hero or anchor_flatlay across all 5. Before each frame, repeat: "Match exact lighting, background, contrast of previous frame."

### Example (reel "Argentina 1986")

```
User: reel argentina 86 maradona

GPT outputs 5 prompts:

F1 (Hook, 0-3s):
STYLE ANCHOR: Match brand-anchor-hero.png.
SCENE: Pure black void gradient.
SUBJECT: Extreme close-up macro shot of vintage light blue jersey
fabric with subtle white stripe. Fabric shows hand-stitched crest
edge at frame bottom-left — just a hint, not fully visible.
DETAILS: Visible vintage cotton weave, tiny fabric imperfections.
LIGHTING: Raked side light from 8 o'clock.
COMPOSITION: 9:16 vertical 1080×1920. Extreme macro, shallow DOF.
CONSTRAINTS: Photorealistic. No text. Quality: high.

F2 (Build, 3-8s):
STYLE ANCHOR: Match F1 exact lighting, background, contrast.
SCENE: Pure black void gradient.
SUBJECT: Medium shot of the full Argentina 1986 away jersey laid
flat, revealing the hand-stitched crest and light blue body with
white stripes.
DETAILS: Jersey occupies 60% of vertical frame. Hand-stitched feel
evident. Le Coq Sportif collar cut. No number visible yet.
LIGHTING: Same as F1.
COMPOSITION: 9:16 vertical. Jersey centered vertically.
CONSTRAINTS: Photorealistic. No text. Quality: high.

F3 (Reveal, 8-14s):
STYLE ANCHOR: Match F1-F2.
SCENE: Pure black void.
SUBJECT: Full Argentina 1986 away jersey, back view, number "10"
visible in period-accurate bold font, occupying upper-center back.
DETAILS: Vintage number "10" styled like 1980s football jersey
printing. Fabric shows slight natural folds.
LIGHTING: Same as F1-F2.
COMPOSITION: 9:16 vertical.
TEXT: No text overlay in image (will be added in edit).
CONSTRAINTS: Photorealistic. EXACT number "10" (digit one and zero),
bold 1980s football font style, white. Quality: high.

F4 (Context, 14-20s):
STYLE ANCHOR: Match F1-F3.
SCENE: Dark wooden archive cabinet with glass doors in pure black
void.
SUBJECT: Argentina 1986 jersey on wooden hanger inside cabinet,
highlighted by warm spotlight. Other jerseys as silhouettes.
DETAILS: Cabinet brass hardware catches rim light.
LIGHTING: Warm spotlight on jersey, everything else in shadow.
COMPOSITION: 9:16 vertical. Cabinet fills 80% of height.
CONSTRAINTS: Photorealistic. Only Argentina jersey colored.
Quality: high.

F5 (CTA, 20-25s):
STYLE ANCHOR: Match F1-F4.
SCENE: Pure black void minimalist.
SUBJECT: Typography-only final frame.
TEXT:
- Center large: "VAULT.ELCLUB.CLUB" in Oswald 700 uppercase,
  white #FFFFFF.
- Below: "Q435 · ENVÍO GRATIS" in Space Grotesk 500, ice blue
  #4DA8FF.
- Bottom: EL CLUB logo small, white.
COMPOSITION: 9:16 vertical. Text centered vertically.
CONSTRAINTS: Typography-focused. No photographic elements.
EXACT text. Quality: high.
```

---

## Historia Mode

**Trigger:** `historia [jersey name]` · e.g. `historia argentina 86` or `historia france 98`

### Core concept
Storytelling post that uses the scripted historia from the 9-historias knowledge. Single-image 1:1 post with hero shot of the jersey + typography treatment of a pull quote from the historia.

### Specs

**Visual:** Product Mode flat lay OR Vault Mode hero (user choice — default to Product flat lay).

**Text overlay:** One pull quote from the historia, typography-driven, Oswald 700 headline + Space Grotesk body.

### Example prompt (`historia argentina 86`)

Reference historia (from 9-historias file):
> "Esta camiseta azul es la que Maradona usó el 22 de junio de 1986
> contra Inglaterra en el Azteca. Al minuto 51 metió la mano, al 55
> se la llevó a cinco ingleses él solo. Bilardo era el DT. Lo que
> casi nadie sabe: Le Coq Sportif no alcanzó a fabricarla, así que
> un dirigente la compró en una tienda del DF y le cosieron el
> escudo a mano."

```
STYLE ANCHOR: Match brand-anchor-flatlay.png.

SCENE: Pure black-to-charcoal gradient.

SUBJECT: Argentina 1986 away jersey laid flat, light blue with white
vertical stripes, hand-stitched crest appearance, Le Coq Sportif
collar cut.

DETAILS: Vintage cotton weave. Number "10" visible on back through
slight turn. Hand-stitched crest feel.

LIGHTING: Key upper-left 2800K warm. Fill right 30%.

COMPOSITION: Bird's eye 90°, 1:1 square. Jersey 60% of frame
(smaller than default, to leave space for text).

TEXT:
- Top third: "LE COSIERON EL ESCUDO" in Oswald 700 uppercase,
  white #FFFFFF, tight tracking. Spelled L-E C-O-S-I-E-R-O-N
  E-L E-S-C-U-D-O.
- Below: "A MANO." in Oswald 700 uppercase, ice blue #4DA8FF.
- Bottom third: "Argentina 1986 — vault.elclub.club" in Space
  Grotesk 400, white small.
- Logo bottom-right.

CONSTRAINTS: Photorealistic. Only jersey colored. EXACT text with
accents. Quality: high.
```

---

## Batch Mode

**Trigger:** `batch` · user provides list of items

### Protocol

1. **Confirm the list** back to the user out loud
2. **Ask which MODE applies** (default Product? Flat lay? Player?)
3. **Generate item 1** at highest quality
4. **For items 2-N:** "match the exact style, lighting, background, and color grading of the previous image"
5. **Consistency check** every 3-4 items: show 4 thumbnails side by side in your chat response. If drift detected → regenerate.
6. **Anchor reference:** use same anchor image across all items

### Example dialog

```
User: batch
Bot: Listo, ¿qué jerseys te genero y en qué mode?
User: producto — Argentina 86 · France 98 · AC Milan 02/03
Bot: Confirmo:
1. Argentina 1986 away (light blue + white)
2. France 1998 home (navy + white + red)
3. AC Milan 2002/03 away (white + red/black)
Mode: Product flat lay. Anchor: brand-anchor-flatlay.png.
Arranco con el #1.
[generates #1]
Bot: Acá va Argentina 86. ¿Seguimos con France 98 manteniendo
misma iluminación y fondo?
```

---

## Anchor generation prompts

Use these 3 prompts to generate the master anchors. Run them in the GPT, download the outputs, upload as knowledge files named:
- `brand-anchor-hero.png`
- `brand-anchor-flatlay.png`
- `brand-anchor-player.png`

### 1. `anchor hero`

```
Generate the master brand anchor image for El Club.

SCENE: Pure black-to-charcoal gradient (#0D0D0D edges, #1C1C1C
center), smooth organic falloff, no vignette.

SUBJECT: Closed kraft cardboard box in the left third of frame,
with a single vibrant red retro football jersey (generic, no specific
team) peeking out from under the box lid on the right side.

DETAILS: Kraft box shows natural cardboard fiber texture, slight
fold lines, one corner with minor wear. Small ice blue #4DA8FF
wax seal on lid. Jersey shows visible cotton weave, hint of white
striping.

LIGHTING: Key light upper-left 2800K warm. Fill right 30% neutral.
Deep shadows behind box, rim light on right edge of jersey. Subtle
matte reflection on surface.

COMPOSITION: 1:1 square 1080×1080. Eye-level 3/4 angle. Box and
jersey together fill 65% of frame, negative space top-right.

CONSTRAINTS: Photorealistic editorial museum-piece photography.
Only the jersey has vibrant color (red). Everything else monochrome
Midnight Stadium palette. No text, no logo, no watermark. Quality: high.
```

### 2. `anchor flatlay`

```
Master flat lay anchor for El Club.

SCENE: Pure black-to-charcoal gradient (#0D0D0D edges, #1C1C1C
center). Smooth organic falloff.

SUBJECT: Single generic retro football jersey laid flat. Generic
design: white body with blue trim on collar and sleeves, no specific
team badge. Sleeves angled 20° outward from body, collar clean at top.

DETAILS: Cotton weave visible, subtle natural fabric folds, no
wrinkles. Clean minimal design.

LIGHTING: Key light upper-left 2800K warm. Fill right 30% neutral.
Subtle matte reflection beneath jersey (not floating). Rim light on
sleeve edges.

COMPOSITION: 1:1 square 1080×1080. Bird's eye 90° top-down.
Jersey 70% of frame, equal padding all sides, centered.

CONSTRAINTS: Photorealistic editorial product photography. No
watermark. Only jersey colored (white + blue trim). Quality: high.
```

### 3. `anchor player`

```
Master player portrait anchor for El Club.

SCENE: Dark stadium haze background — blurred blacks and dark blues
(#0D0D0D with hints of #1C2A3A), subtle bokeh of distant stadium
floodlights, atmospheric fog. Never a recognizable real stadium.

SUBJECT: Generic athletic male figure, mid-20s, fit build, face
partially obscured by shadow and 3/4 angle. Wearing a generic red
retro football jersey (no specific team or name). Chest slightly
forward, shoulders square, serious contemplative gaze slightly
off-camera.

DETAILS: Jersey shows clear fabric weave, visible crest area
(generic, no specific team), clean collar. Skin warm with natural
tones. Short dark hair.

LIGHTING: Rembrandt-style key light upper-left (creates triangle
of light on shadow side of cheek). Strong rim light on right
shoulder/hair separating him from background. Subtle cool fill
#1C2A3A on shadow side. BRIGHTEST LIGHT FALLS ON JERSEY — chest
and torso fully readable, crest clearly lit. Face partially in shadow.

COMPOSITION: 4:5 portrait 1080×1350. Chest-up framing. Camera
slightly below eye level. Jersey is the LARGEST area of the image.

CONSTRAINTS: Photorealistic editorial cinematic portrait. Teal-and-
orange cinema grade skewed dark. Skin warm not orange. Jersey color
100% accurate (vibrant red). No smiling, no celebrating, no action.
No recognizable stadium. No watermark. Quality: high.
```

---

## Las 9 historias del catálogo

Source: `elclub-catalogo-priv/data/catalog.json`

Usá estas historias tal cual (voseo, estilo, datos ya curados). Al generar un `historia [X]` post, sacá un pull quote potente de acá.

### 1. AC Milan 02/03 away (Tier 1 · Retro premium)
> La blanca que Milan usó contra la Juventus en la final de Champions el 28 de mayo de 2003 en Old Trafford. 0-0 después de 120 minutos y Shevchenko metió el penal decisivo para el 3-2. Ancelotti era el DT y Maldini levantó la copa 40 años después de que su papá Cesare hiciera lo mismo. Primera final 100% italiana de la UCL. Opel de patrocinador, Adidas de marca. Juventus no volvió a ganar una Champions, fijate.

### 2. Argentina 2026 home (Tier 1 · Mundial)
> La de las tres estrellas en el escudo (1978, 1986, 2022) y la de Messi #10 todavía de capitán a los 38. Scaloni sigue al frente. Ganaron la Copa América 2024 contra Colombia 1-0 con gol de Lautaro Martínez al 112, y fueron los primeros de Sudamérica en clasificar al Mundial 2026. Dibu Martínez con su #23 atrás. Adidas. Si no la tenés ahora, tenés que esperar otro Mundial para verla así de cargada. Suerte con eso.

### 3. Brazil 2026 home (Tier 1 · Mundial)
> La amarilla canarinha que busca la sexta Copa, porque la quinta fue en 2002 y ya se hizo largo. Carlo Ancelotti es el DT desde mayo de 2025, contratado después de que despidieran a Dorival Júnior por el 4-1 que les metió Argentina en marzo. Vinicius Jr con el #7. Copa América 2024 la perdieron en cuartos contra Uruguay por penales. Nike sigue fabricándola. Contratar italiano para ganarle a Argentina, mirá vos.

### 4. Mexico 2026 home (Tier 1 · Mundial)
> La verde del tercer Mundial como anfitrión: 1970, 1986 y ahora 2026, el único país que lo hace tres veces. El Azteca arranca el torneo el 11 de junio contra Sudáfrica. Javier Aguirre está de DT por tercera vez — sabés que si te llaman tres veces es porque nadie más quiere. Adidas la fabrica. Y ahí anda la maldición del quinto partido: México no pasa de octavos desde 1994. Esta vez juegan en casa, quizás.

### 5. Real Madrid 26/27 home (Tier 1 · Actual)
> La blanca merengue con 15 Champions en el pecho, la última en junio de 2024 contra el Dortmund 2-0 en Wembley. Mbappé llegó desde el PSG ese verano, arrancó con el #9 y tomó el #10 cuando se fue Modrić. Bellingham #5, Vinicius #7. Ancelotti se fue a dirigir a Brasil, Xabi Alonso duró siete meses y Arbeloa está de interino. Adidas. Bernabéu remodelado. En Madrid siempre hay crisis, sabés cómo es.

### 6. Spain 2026 home (Tier 1 · Mundial)
> La roja que ganó la Eurocopa 2024 el 14 de julio en Berlín contra Inglaterra 2-1, con gol de Oyarzabal al 86. Luis de la Fuente sigue siendo el DT hasta 2028. Lamine Yamal con el #19 a los 16 fue el jugador joven del torneo. Rodri ganó el Balón de Oro ese año, el primer español en 64 años. Cuarta Eurocopa para España, récord. Adidas la fabrica. La mejor generación desde Xavi-Iniesta, fijate.

### 7. Albania 2026 third (Tier 2 · Easter egg de marca)
> Albania se queda fuera del Mundial 2026, pero vos sabés que los verdaderos hinchas no dejan de apoyar. Esta tercera camiseta es para los que creen en el equipo más allá de clasificaciones. Midnight Stadium la trae en su versión más oscura y sofisticada, porque el orgullo balcánico no se negocia.

### 8. Argentina 1986 away (Tier 3 · HERO RARITY)
> Esta camiseta azul es la que Maradona usó el 22 de junio de 1986 contra Inglaterra en el Azteca. Al minuto 51 metió la mano, al 55 se la llevó a cinco ingleses él solo. Bilardo era el DT. Lo que casi nadie sabe: Le Coq Sportif no alcanzó a fabricarla, así que un dirigente la compró en una tienda del DF y le cosieron el escudo a mano. Argentina terminó ganando su segunda Copa contra Alemania. Mirá vos.

### 9. France 1998 home (Tier 3 · Retro-joya)
> La que Zidane usó el 12 de julio de 1998 en el Stade de France para meter dos cabezazos contra Brasil: uno al minuto 27, otro al 45+1. Petit la cerró 3-0 en el descuento. Aimé Jacquet era el DT, Deschamps el capitán. Francia ganó su primera Copa con un plantel black-blanc-beur que cambió cómo se veía al país. Adidas la hizo. Y sabés qué, Ronaldo tuvo una convulsión horas antes del partido que nadie ha explicado bien.

---

## Pricing

| Producto | Precio | Notas |
|----------|--------|-------|
| **Mystery Box Clásica** ⭐ | **Q350** | 1 camiseta curada · HERO product |
| Combo Mystery Box | Q650 | 2 camisetas curadas · mejor valor |
| Catálogo El Club | Q450 | Jersey elegido del stock público |
| Garantizada | Q475 | Jersey específico garantizado |
| On-demand | Q425 | Jersey no en stock, sourcing |
| **Vault** | **Q435** | Catálogo privado vault.elclub.club |
| Personalización | +Q15 | Sobre combo (nombre + dorsal) |

**Envío:** Gratis en Guatemala.
**Pagos:** Recurrente (tarjeta) · transferencia · contra entrega.
**WhatsApp:** +1 318 534-3283
**Sitio público:** elclub.club
**Vault privado:** vault.elclub.club

---

## Troubleshooting común

### El output sale demasiado oscuro (casi negro puro)
**Fix:** agregá al CONSTRAINTS: `readable exposure, not crushed to pure black, visible fabric texture and details throughout`.

### El fondo sale gris plano (no gradient)
**Fix:** en SCENE repetí: `smooth organic gradient falloff from #0D0D0D at edges to #1C1C1C at center, NOT flat gray, NOT pure black`.

### El jersey se ve como render CGI
**Fix:** CONSTRAINTS: `photorealistic photograph, not 3D render, visible cotton/polyester weave texture, natural fabric imperfections, subtle wear`. Si persiste → regenerar.

### El color del jersey no coincide con la referencia
**Fix:** especificar hex exactos del jersey: `jersey body color exact RGB match to reference Image 1, do not shift hue or saturation`.

### El texto en la imagen sale con errores (misspellings)
**Fix:**
1. Spell letter-by-letter en prompt
2. Quality: high
3. Wrap en QUOTES
4. Pedí explícitamente: `EXACT text rendering, no extra characters, no substitutions, preserve accents (á é í ó ú ñ) exactly`
5. Si persiste → generá sin texto y agregá en Canva/Figma

### Genera múltiples jerseys cuando pedí uno
**Fix:** SUBJECT: `a SINGLE football jersey, one only, not multiple, not a collection`.

### Player sonríe cuando pedí serio
**Fix:** player portrayal: `no smile, neutral expression, pre-match contemplative gaze, do not smile, do not laugh`.

### Drift entre posts consecutivos (pierde consistencia)
**Fix:**
1. Re-anchor en cada prompt: `Match exact lighting/background/grading/contrast of brand-anchor-[type].png`
2. Después de 3-4 posts, mostrá 4 thumbnails side-by-side y pedí "consistency check"

### Logo agregado incorrectamente o con errores
**Fix:** si el logo viene del knowledge file, pedí: `use the exact EL CLUB logo from knowledge file logo-elclub-dark.png, preserve proportions, do not modify, place bottom-right`.

---

*Fin del playbook. Consultá este archivo antes de cada generación.
Si algo cambia en BRAND.md, actualizá este playbook también.*
