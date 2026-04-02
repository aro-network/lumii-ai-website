```markdown
# Design System: Technical Etherealism

## 1. Overview & Creative North Star: "The Digital Fog"
This design system moves away from the rigid, boxed-in layouts of traditional documentation and developer tools, pivoting toward **Technical Etherealism**. The objective is to maintain a high-precision, monochromatic aesthetic while removing the "industrial friction" of hard edges and high-contrast dividers.

**The Creative North Star: "The Digital Fog"**
Imagine a high-end laboratory at dawn. Everything is precise, technical, and clean, but the light is soft, and surfaces bleed into one another. We achieve this through **Atmospheric Layering**: using subtle gradients, diffused shadows, and tonal shifts rather than lines to define architecture. The result is a premium, editorial experience that feels engineered yet breathable.

---

## 2. Colors & Surface Logic
The palette is a sophisticated range of greys and off-whites designed to create depth without visual noise.

### The "No-Line" Rule
**Explicit Instruction:** Designers are prohibited from using 1px solid, high-contrast borders to separate sections. Structure must be defined by:
1.  **Tonal Transitions:** Moving from `surface` (#f9f9f9) to `surface-container-low` (#f2f4f4).
2.  **Soft Fades:** Using vertical linear gradients (e.g., `surface` to `surface-container`) over a 160px transition zone to blend major sections like the Hero and Value Prop.

### Surface Hierarchy & Nesting
Instead of a flat grid, treat the UI as stacked sheets of vellum.
*   **Base Layer:** `surface` (#f9f9f9)
*   **Sectional Shift:** `surface-container-low` (#f2f4f4) for secondary content areas.
*   **Feature Focus:** `tertiary-container` (#f3f3f3) for the "softer" dark grey value proposition sections, ensuring a gentle blend into the white surroundings.
*   **Interactive Floating:** `surface-container-lowest` (#ffffff) for cards or code blocks to make them "pop" against darker tinted backgrounds.

### The Glass & Gradient Rule
To achieve "visual soul," primary CTAs and the "glowing" logo focal point should utilize `surface-tint` (#5e5e5e) with a subtle radial gradient. For floating navigation or modals, apply **Glassmorphism**:
*   **Background:** `surface-container-lowest` at 70% opacity.
*   **Effect:** `backdrop-blur` (20px).
*   **Result:** The UI feels integrated into the environment rather than "pasted" on top.

---

## 3. Typography: The Engineering Editorial
We pair the technical rigor of **Space Grotesk** with the functional clarity of **Inter**.

*   **Display & Headlines (Space Grotesk):** These are your "Structural Landmarks." Use `display-lg` (3.5rem) with tight letter-spacing (-0.02em) to create an authoritative, technical presence.
*   **Body & Utility (Inter):** Used for long-form reading and data. The `body-md` (0.875rem) provides the necessary legibility to balance the expressive nature of the headlines.
*   **The Signature Scale:** We break the "template" look by using extreme contrast between `display-lg` and `label-sm`. This intentional asymmetry mirrors high-end architectural blueprints.

---

## 4. Elevation & Depth: Atmospheric Layering
Traditional shadows are too heavy for this system. We use **Ambient Depth**.

*   **The Layering Principle:** Place a `surface-container-lowest` card on a `surface-container-low` background. The subtle shift in hex value creates enough contrast for the eye to perceive depth without a single pixel of shadow.
*   **Ambient Shadows:** When a "lift" is required (e.g., for a floating code block), use a highly diffused shadow:
    *   **Blur:** 24px - 40px.
    *   **Opacity:** 4% - 6% of `on-surface` (#2d3435).
    *   **Spread:** -5px to keep the shadow tucked under the element, mimicking soft overhead studio lighting.
*   **The "Ghost Border":** If accessibility requires a container boundary, use `outline-variant` (#adb3b4) at **10% opacity**. It should be felt, not seen.

---

## 5. Components

### Buttons
*   **Primary:** Background `primary` (#5e5e5e), text `on-primary` (#f8f8f8). Roundedness: `md` (0.75rem). No shadow; use a subtle 10% inner-glow on hover.
*   **Secondary:** Background `surface-container-high`, no border.
*   **Tertiary:** Ghost style. No background/border. Use `label-md` for a technical, "button-less" aesthetic.

### Cards & Code Blocks
*   **Styling:** Never use dividers. Separate internal content with `spacing-6` (2rem).
*   **Code Blocks:** Use `tertiary-dim` (#525354) for the background with a `sm` (0.25rem) "Ghost Border" to define the technical edge. Apply the Ambient Shadow for depth.

### Input Fields
*   **Styling:** Abandon the 4-sided box. Use a `surface-container-highest` background with a `2px` bottom-only highlight in `primary` when focused. This creates a "terminal" feel that aligns with the developer aesthetic.

### Chips
*   **Action Chips:** Use `full` roundedness and `surface-container-low`. They should look like smooth pebbles, inviting interaction without the "sharpness" of standard UI tags.

---

## 6. Do’s and Don’ts

### Do:
*   **Use Asymmetry:** Align text to the left but allow imagery or code blocks to bleed off the right edge of the grid.
*   **Embrace Whitespace:** Use `spacing-24` (8.5rem) between major sections to let the "Digital Fog" (gradients) breathe.
*   **Glow Responsibly:** The "glowing" logo is the focal point. Ensure it uses a `primary-fixed-dim` outer glow to act as a light source for the rest of the header.

### Don’t:
*   **Don't use #000000:** Total black is too jarring. Use `inverse_surface` (#0c0f0f) for the deepest tones.
*   **Don't use hard dividers:** If you feel the need for a line, use a `1.5` (0.5rem) height gap with a color shift instead.
*   **Don't use standard "Drop Shadows":** If the shadow looks like a "fuzzy grey box," the blur radius is too small. Double it and halve the opacity.

### Accessibility Note:
While we use low-contrast borders, ensure that text-to-background contrast ratios always meet WCAG AA standards using the `on-surface` and `on-background` tokens. The "Ghost Border" is a visual flourish, not a functional requirement for element recognition.```