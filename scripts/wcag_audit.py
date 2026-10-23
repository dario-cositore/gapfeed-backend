import colorsys

def hex_to_rgb(h):
    h = h.lstrip('#')
    if len(h) == 3:
        h = ''.join(c*2 for c in h)
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def relative_luminance(r, g, b):
    def linearize(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)

def contrast_ratio(l1, l2):
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)

WHITE_LUM = relative_luminance(255, 255, 255)

# Colors to check against white
colors = {
    "#111": "text primary",
    "#FF6B00": "accent orange",
    "#CC5500": "accent dark",
    "#D05500": "accent mid",
    "#A04000": "accent dark option",
}

print("=== CONTRAST vs WHITE (#fff) ===")
for hex_c, label in colors.items():
    r, g, b = hex_to_rgb(hex_c)
    lum = relative_luminance(r, g, b)
    cr = contrast_ratio(WHITE_LUM, lum)
    normal = "PASS" if cr >= 4.5 else "FAIL"
    large = "PASS" if cr >= 3.0 else "FAIL"
    print(f"  {hex_c} ({label}): {cr:.2f}:1 — normal={normal}, large={large}")

# RGBA values on white
print("\n=== RGBA on WHITE ===")
rgba_values = {
    0.5: "text-dim",
    0.45: "text-mid",
    0.4: "text-dim-alt",
    0.35: "text-muted",
}
for opacity, label in rgba_values.items():
    lum = relative_luminance(255*opacity, 255*opacity, 255*opacity)
    cr = contrast_ratio(WHITE_LUM, lum)
    normal = "PASS" if cr >= 4.5 else "FAIL"
    print(f"  rgba(0,0,0,{opacity}) ({label}): {cr:.2f}:1 — normal={normal}")

# Find a good orange that passes 4.5:1 against white
print("\n=== FINDING ACCESSIBLE ORANGE ===")
for r in range(160, 255, 5):
    for g in range(50, 130, 5):
        for b in [0, 10, 20]:
            lum = relative_luminance(r, g, b)
            cr = contrast_ratio(WHITE_LUM, lum)
            if 4.45 <= cr <= 4.6 and 180 <= r <= 220:
                hex_c = f"#{r:02X}{g:02X}{b:02X}"
                print(f"  {hex_c} (r={r},g={g},b={b}): {cr:.2f}:1")
