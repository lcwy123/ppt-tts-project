import zipfile
import re

with zipfile.ZipFile('data/output/generated.pptx', 'r') as z:
    files = z.namelist()

    # Check presentation.xml for layout references
    pres = z.read('ppt/presentation.xml').decode('utf-8')

    # Find all layout references
    layouts = re.findall(r'Target="([^"]*slideLayout[^"]+)"', pres)
    print(f'Layout references in presentation.xml: {len(layouts)}')

    # Check if referenced layouts exist
    for layout in layouts[:5]:
        path = 'ppt/' + layout.replace('../', '')
        if path in files:
            print(f'OK: {layout}')
        else:
            print(f'MISSING: {layout}')

    # Check if all slideLayouts exist
    slide_layouts = [f for f in files if 'slideLayout' in f and f.endswith('.xml') and '_rels' not in f]
    print(f'\\nTotal slideLayouts: {len(slide_layouts)}')

    # Check presentation.xml for slide references
    sld_leafs = re.findall(r'Target="([^"]*slides/slide[^"]+)"', pres)
    print(f'\\nSlide references in presentation.xml: {len(sld_leafs)}')

    # Check all slides exist
    slides = [f for f in files if f.startswith('ppt/slides/slide') and f.endswith('.xml') and '_rels' not in f]
    print(f'Total slide files: {len(slides)}')