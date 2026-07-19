import os
import glob
import re

views_dir = r"D:\My projects\VPN\OverREALITY\src\RealityTunnel.OperationsConsole\Views"
for filepath in glob.glob(os.path.join(views_dir, "*.xaml")):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    new_content = content.replace("AncestorType=DataGrid", "AncestorType={x:Type DataGrid}")
    new_content = new_content.replace("AncestorType=ItemsControl", "AncestorType={x:Type ItemsControl}")
    new_content = new_content.replace("AncestorType=ListView", "AncestorType={x:Type ListView}")
    
    if new_content != content:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Fixed {os.path.basename(filepath)}")
