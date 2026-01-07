#!/usr/bin/env bash
# 🔴 RedLight Template System
# Brand-consistent HTML templates for BlackRoad

# Template directory
TEMPLATE_DIR="${TEMPLATE_DIR:-.trinity/redlight/templates}"

# Function to list available templates
list_templates() {
    echo "🔴 Available RedLight Templates:"
    echo ""
    if [ -d "$TEMPLATE_DIR" ]; then
        ls -1 "$TEMPLATE_DIR"/*.html 2>/dev/null || echo "No templates found in $TEMPLATE_DIR"
    else
        echo "Template directory not found: $TEMPLATE_DIR"
    fi
    echo ""
}

# Function to copy a template
copy_template() {
    local template_name="$1"
    local destination="$2"
    
    if [ -z "$template_name" ] || [ -z "$destination" ]; then
        echo "Usage: copy_template <template_name> <destination>"
        return 1
    fi
    
    local template_path="$TEMPLATE_DIR/$template_name"
    
    if [ ! -f "$template_path" ]; then
        echo "❌ Template not found: $template_path"
        return 1
    fi
    
    cp "$template_path" "$destination"
    echo "✅ Template copied to: $destination"
}

# Function to show brand colors
show_brand_colors() {
    echo "🎨 BlackRoad Brand Colors:"
    echo ""
    echo "  Amber:        #FF9500  rgb(255, 149, 0)"
    echo "  Hot Pink:     #FF2D55  rgb(255, 45, 85)"
    echo "  Violet:       #9F86FF  rgb(159, 134, 255)"
    echo "  Electric Blue: #00C7FF  rgb(0, 199, 255)"
    echo ""
    echo "Gradient: Amber → Hot Pink → Violet → Electric Blue"
    echo ""
}

# Function to validate HTML
validate_template() {
    local file="$1"
    
    if [ -z "$file" ]; then
        echo "Usage: validate_template <file.html>"
        return 1
    fi
    
    if [ ! -f "$file" ]; then
        echo "❌ File not found: $file"
        return 1
    fi
    
    echo "🔍 Validating $file..."
    
    # Check for required meta tags
    if ! grep -q 'meta charset="UTF-8"' "$file"; then
        echo "⚠️  Missing charset meta tag"
    fi
    
    if ! grep -q 'meta name="viewport"' "$file"; then
        echo "⚠️  Missing viewport meta tag"
    fi
    
    # Check for title
    if ! grep -q '<title>' "$file"; then
        echo "⚠️  Missing title tag"
    fi
    
    # Check for brand colors
    local has_brand_color=false
    for color in "#FF9500" "#FF2D55" "#9F86FF" "#00C7FF"; do
        if grep -q "$color" "$file"; then
            has_brand_color=true
            break
        fi
    done
    
    if [ "$has_brand_color" = true ]; then
        echo "✅ Brand colors detected"
    else
        echo "⚠️  No brand colors found"
    fi
    
    echo "✅ Validation complete"
}

# Function to create a basic template
create_basic_template() {
    local filename="$1"
    
    if [ -z "$filename" ]; then
        echo "Usage: create_basic_template <filename.html>"
        return 1
    fi
    
    cat > "$filename" << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BlackRoad - Your Title</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #FF9500, #FF2D55, #9F86FF, #00C7FF);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
        }
        
        .container {
            text-align: center;
            padding: 2rem;
            max-width: 800px;
        }
        
        h1 {
            font-size: clamp(2rem, 5vw, 4rem);
            font-weight: 700;
            margin-bottom: 1rem;
        }
        
        p {
            font-size: clamp(1rem, 2vw, 1.5rem);
            font-weight: 300;
            opacity: 0.9;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🌈 BlackRoad</h1>
        <p>Your content here</p>
    </div>
</body>
</html>
EOF
    
    echo "✅ Basic template created: $filename"
}

# Help function
show_help() {
    echo "🔴 RedLight Template System - Commands"
    echo ""
    echo "  list_templates                    - List available templates"
    echo "  copy_template <name> <dest>       - Copy a template"
    echo "  show_brand_colors                 - Show brand color palette"
    echo "  validate_template <file>          - Validate HTML template"
    echo "  create_basic_template <file>      - Create a basic branded template"
    echo "  show_help                         - Show this help"
    echo ""
}

# Export functions
export -f list_templates
export -f copy_template
export -f show_brand_colors
export -f validate_template
export -f create_basic_template
export -f show_help

echo "🔴 RedLight Template System loaded"
echo "Run 'show_help' for available commands"
