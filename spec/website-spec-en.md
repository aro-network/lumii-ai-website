# LumiiAI Website Specification

**Target:** International developers  
**Tool:** Stitch / Figma  
**Style:** Clean, technical, developer oriented, NOT enterprise style

---

## 1. Visual Identity

### 1.1 Brand Personality

- **Technical but approachable**
- **Transparent & trustworthy**
- **Developer-focused, no marketing fluff**

### 1.2 Color Theme

- Black & White & Grey
- Color Palette: Monochromatic grayscale. UI components use black, white, and shades of gray only. High contrast for readability. Links styled with underline or bold weight instead of color. Photography and media retain natural colors. No chromatic accents in interface elements.
- WHITE Background， WHITE Background


---

## 2. Page Structure

### 2.1 Hero Section

**Layout:** 2-column (text left, code right)

**Left Column - Content:**
```
Headline:
Clean & Stable AI token API access.

Subheadline:
Direct Sourced. Operationally excellent. Not a Marketplace.

CTA Buttons:
[Get Started]  [View Docs]
```

**Right Column - Code Snippet:**
```python
import openai

client = openai.OpenAI(
    base_url="https://api.lumii-ai.io/v1",
    api_key="your-key"
)

response = client.chat.completions.create(
    model="lumii-auto",
    messages=[{"role": "user", "content": "Hello"}]
)
```

- Syntax highlighted
- Dark code block on light background
- Copy button in top-right corner
- Language label (Python)

**Visual:** 
- WHITE background (light mode)
- Clean, minimal
- No stock photos
- Code block has subtle shadow or border

---

### 2.2 Value Proposition Section

**Layout:** 3-column grid

**Content:**
```
Card 1:
Direct Sourced
Models sourced directly from providers. No middlemen.

Card 2:
Operationally Excellent
Lean ops, quality infrastructure, stable delivery.

Card 3:
Clean & Stable
No bait-and-switch. Just reliable API access.
```

**Visual:** 
- Simple icons for each card
- Clean cards on light background
- Minimal decoration

---

### 2.3 What We Offer Section

**Layout:** 2-column (text left, visual right)

**Content:**
```
Headline:
Everything You Expect

List:
• Smart routing (lumii-auto)
• Multiple payment options  
• Multiple API formats
• Transparent pricing
• Model verification
• Pay-as-you-go, crypto supported

Subtext:
Table stakes. The real value is stability from direct source & operation.
```

---

### 2.4 How It Works Section

**Layout:** Simple 3-step flow

**Content:**
```
Step 1: Sign Up
Create account, add payment method

Step 2: Get API Key
One key for all models

Step 3: Start Building
Point your code to our endpoint
```

**Visual:**
- Simple numbered steps
- Minimal icons
- Horizontal flow

---

### 2.5 Pricing Section

**Layout:** Simple table or cards

**Content:**
```
Headline:
Simple, Transparent Pricing

Model Categories:
Open Source Models: From $0.10/1M tokens
Premium Models: Competitive rates
lumii-auto: Optimized pricing

Note:
Pay-as-you-go. No monthly fees. No hidden costs.
```

---

### 2.6 Footer

**Content:**
```
Logo + Tagline

Links:
- Documentation
- API Reference
- Status
- Support
- Terms
- Privacy

Social:
- Twitter/X
- Discord
- GitHub

Copyright © 2026 LumiiAI
```

---

## 3. Key Pages

### 3.1 Homepage (above)

### 3.2 Documentation Page
- Getting started guide
- API reference
- Code examples
- Model list

### 3.3 Dashboard (after login)
- API key management
- Usage stats
- Billing history
- Model verification logs

---

## 4. Interactive Elements

### 4.1 Code Snippet (Hero or How It Works)

```
import openai

client = openai.OpenAI(
    base_url="https://api.lumii-ai.io/v1",
    api_key="your-key"
)

response = client.chat.completions.create(
    model="lumii-auto",
    messages=[{"role": "user", "content": "Hello"}]
)
```

- Syntax highlighted
- Copy button
- Dark code block

---

## 5. Responsive Design

- **Desktop:** Full layout, side-by-side sections
- **Tablet:** Stacked sections, 2-column where appropriate
- **Mobile:** Single column, hamburger menu

---

## 6. Copy Guidelines

**Do:**
- Keep it simple and direct
- Use technical language when appropriate
- Focus on stability and trust
- Show, don't just tell

**Don't:**
- Use marketing fluff ("revolutionary", "game-changing")
- List every single model by name
- Over-explain the technology
- Use stock photos of happy developers

---

## 7. File Deliverables

For Stitch/Figma generation:

1. `lumiiAI-homepage` - Main landing page
2. `lumiiAI-docs` - Documentation page template
3. `lumiiAI-dashboard` - User dashboard template

---

## 8. Notes When Generating

**CRITICAL CONSTRAINTS - MUST FOLLOW:**

1. **DO NOT CHANGE ANY TEXT** - Use exact text from this spec
2. **DO NOT MAKE UP NUMBERS** - Only use numbers explicitly stated above
3. **DO NOT MAKE UP PRICES** - Pricing must match Section 2.5 exactly:
   - Open Source Models: From $0.10/1M tokens
   - Premium Models: Competitive rates
   - lumii-auto: Optimized pricing
4. **DO NOT MAKE UP MODEL NAMES** - Only mention "lumii-auto" as the model name
5. **DO NOT ADD FAKE TESTIMONIALS OR STATS** - No "10,000+ users" or "99.9% uptime" unless stated above

---


*Spec for LumiiAI Website v1.0*  
*Date: 2026-04-01*
