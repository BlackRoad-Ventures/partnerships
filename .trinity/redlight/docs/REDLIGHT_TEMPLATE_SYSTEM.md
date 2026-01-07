# 🔴 RedLight - Template & Brand System

## Overview

RedLight is BlackRoad's unified template and brand system, ensuring visual consistency across all digital properties.

## Brand Guidelines

### Colors
- **Primary Gradient:** Amber → Hot Pink → Violet → Electric Blue
- **Amber:** `#FF9500` / `rgb(255, 149, 0)`
- **Hot Pink:** `#FF2D55` / `rgb(255, 45, 85)`
- **Violet:** `#9F86FF` / `rgb(159, 134, 255)`
- **Electric Blue:** `#00C7FF` / `rgb(0, 199, 255)`

### Typography
- **Primary:** SF Pro Display
- **Fallback:** `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
- **Weights:** 300 (light), 400 (regular), 600 (semibold), 700 (bold)

### Design Principles
- **Golden Ratio:** φ = 1.618 for spacing and proportions
- **Responsive:** Mobile-first, fluid scaling
- **Accessible:** WCAG 2.1 AA compliance
- **Performant:** Optimized assets, minimal dependencies

## Template Categories

### Landing Pages
Professional landing pages with:
- Hero sections with gradient backgrounds
- Feature showcases
- Call-to-action sections
- Responsive navigation

### Animations
Interactive experiences featuring:
- CSS/JS animations
- Scroll-triggered effects
- Particle systems
- 3D transformations

### 3D Worlds
Immersive 3D environments using:
- Three.js integration
- WebGL shaders
- Interactive camera controls
- Performance optimization

## Usage

### Starting a New Page

```bash
# Source the template system
source .trinity/redlight/scripts/memory-redlight-templates.sh

# List available templates
ls .trinity/redlight/templates/

# Copy a template
cp .trinity/redlight/templates/blackroad-ultimate.html ./my-page.html
```

### Customization Guidelines

1. **Keep the brand colors** - Use the defined gradient
2. **Maintain spacing ratios** - Follow golden ratio principles
3. **Preserve accessibility** - Don't remove ARIA labels
4. **Optimize assets** - Compress images, minify code
5. **Test responsiveness** - Verify mobile, tablet, desktop

## Template Structure

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <!-- Meta tags -->
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  
  <!-- Title and description -->
  <title>Your Page Title</title>
  
  <!-- Styles (inline for performance) -->
  <style>
    /* Brand colors */
    /* Typography */
    /* Layouts */
    /* Animations */
  </style>
</head>
<body>
  <!-- Navigation -->
  <!-- Hero section -->
  <!-- Content sections -->
  <!-- Footer -->
  
  <!-- Scripts (defer for performance) -->
  <script>
    // Animations
    // Interactions
  </script>
</body>
</html>
```

## Best Practices

### Performance
- ✅ Inline critical CSS
- ✅ Defer non-critical JavaScript
- ✅ Optimize images (WebP, AVIF)
- ✅ Use system fonts when possible
- ✅ Minimize HTTP requests

### Accessibility
- ✅ Semantic HTML
- ✅ ARIA labels for interactive elements
- ✅ Keyboard navigation support
- ✅ Color contrast ratios (4.5:1 minimum)
- ✅ Focus indicators

### Responsiveness
- ✅ Mobile-first approach
- ✅ Fluid typography (clamp, vw units)
- ✅ Flexible layouts (flexbox, grid)
- ✅ Touch-friendly targets (44px minimum)
- ✅ Viewport-aware animations

## Contributing

To add new templates:

1. Follow brand guidelines
2. Test across browsers (Chrome, Firefox, Safari, Edge)
3. Validate HTML (W3C validator)
4. Check accessibility (axe, WAVE)
5. Document usage examples
6. Submit to `blackroad-os/blackroad-os-infra`

---

**"Consistency breeds excellence."** 🔴✨
