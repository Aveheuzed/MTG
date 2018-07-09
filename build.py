#!/usr/bin/env python3.7

import zipapp, pathlib

def pathfilter(path):
    path = pathlib.Path(path)
    if path.name in ("__main__.py", "back.jpeg") :
        return True
    return False

here = pathlib.Path(__file__)
zipapp.create_archive(here.parent,
                      interpreter="/usr/bin/env python3",
                      target=here.parent.parent/"MTG.pyz",
                      filter=pathfilter,
                      compressed=True)
