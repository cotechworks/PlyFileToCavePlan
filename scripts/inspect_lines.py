p=r'd:\\SynologyDrive\\Document\\SoftwareDevelopment\\Python\\PlyFileToCavePlan\\plyfile_gui.py'
with open(p,'r',encoding='utf-8') as f:
    lines=f.readlines()
for i in range(240,270):
    print(i+1, repr(lines[i]))
