"""
PWA Icon Generator - Create black & white skewed icons
"""

def generate_pwa_icon_svg(size=192, skew=15):
    """
    Generate a stylized PWA icon (black & white, skewed)
    
    Args:
        size: Icon size in pixels
        skew: Skew angle in degrees
    
    Returns:
        SVG string
    """
    return f'''
    <svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <style>
                @media (prefers-color-scheme: dark) {{
                    .bg {{ fill: #ffffff; }}
                    .fg {{ fill: #000000; }}
                }}
                @media (prefers-color-scheme: light) {{
                    .bg {{ fill: #000000; }}
                    .fg {{ fill: #ffffff; }}
                }}
            </style>
        </defs>
        
        <!-- Background -->
        <rect width="{size}" height="{size}" class="bg"/>
        
        <!-- Skewed foreground shape -->
        <g transform="skewX({skew})">
            <!-- Map pin -->
            <path d="M {size//2} {size//4} C {size//3} {size//4} {size//4} {size//3} {size//4} {size//2} C {size//4} {size*3//4} {size//2} {size*7//8} {size//2} {size*7//8} C {size*3//4} {size*3//4} {size*3//4} {size//3} {size*3//4} {size//2} C {size*3//4} {size//4} {size*2//3} {size//4} {size//2} {size//4} Z" 
                  class="fg" fill-rule="evenodd"/>
            
            <!-- Inner circle dot -->
            <circle cx="{size//2}" cy="{size//2}" r="{size//8}" class="bg"/>
        </g>
        
        <!-- Heatmap indicator (small bars) -->
        <g transform="translate({size*3//4}, {size//4})">
            <rect x="0" y="0" width="4" height="8" class="fg" opacity="0.3"/>
            <rect x="6" y="0" width="4" height="12" class="fg" opacity="0.6"/>
            <rect x="12" y="0" width="4" height="16" class="fg" opacity="1"/>
        </g>
    </svg>
    '''

def generate_pwa_icons():
    """Generate all PWA icon sizes"""
    icons = {}
    sizes = [192, 512]
    
    for size in sizes:
        # Regular icon
        icons[f'icon-{size}.svg'] = generate_pwa_icon_svg(size, skew=15)
        
        # Maskable icon (for iOS)
        icons[f'icon-maskable-{size}.svg'] = generate_pwa_icon_svg(size, skew=0)
    
    return icons

if __name__ == '__main__':
    icons = generate_pwa_icons()
    for name, svg in icons.items():
        with open(f'/workspaces/templako/backend/static/{name}', 'w') as f:
            f.write(svg)
        print(f"✓ Generated {name}")
