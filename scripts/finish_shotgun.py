"""Finish the supplied blockout. Run in Blender 5.0+ with --python, or using bpy.
All paths resolve relative to this file; the source blockout is never overwritten.
"""
import bpy, bmesh, math, os, json
from pathlib import Path
from mathutils import Vector
from math import sin, cos, pi

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'Shotgun_Animation_Kit' / 'Shotgun_Blockout.blend'
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
if bpy.context.object and bpy.context.object.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
scene = bpy.context.scene
for obj in list(bpy.data.objects):
    if obj.type not in {'MESH'}: bpy.data.objects.remove(obj, do_unlink=True)
for col in list(bpy.data.collections):
    if not col.objects and not col.children: bpy.data.collections.remove(col)

# Model geometry uses X for width, +Y toward the muzzle, Z upward.
model = bpy.data.collections.new('SHOTGUN | model')
scene.collection.children.link(model)
rigcol = bpy.data.collections.new('RIG | animated controls')
scene.collection.children.link(rigcol)
studio = bpy.data.collections.new('STUDIO | cameras and lights')
scene.collection.children.link(studio)
refs = bpy.data.collections.new('REFERENCES | packed images')
scene.collection.children.link(refs)
refs.hide_render = True

def move(obj, collection=model):
    for c in list(obj.users_collection): c.objects.unlink(obj)
    collection.objects.link(obj)
    return obj

def material(name, color, metal=0, rough=.4):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Metallic'].default_value=metal; p.inputs['Roughness'].default_value=rough
    return m
steel=material('01 | blued iron',(.038,.062,.075),.85,.29)
edge=material('02 | brushed steel',(.19,.25,.27),.83,.32)
gold=material('03 | antique brass',(.52,.29,.085),.78,.3)
bright=material('04 | engraved brass',(.76,.51,.19),.72,.29)
black=material('05 | recesses',(.008,.012,.015),.2,.48)
wood=material('06 | walnut',(.19,.042,.025),.0,.36)
leather=material('07 | oxblood leather',(.16,.022,.018),.0,.55)
gem=material('08 | turquoise enamel',(.018,.38,.4),.5,.22)
# Fine, subdued procedural wood grain; no external texture dependency.
n=wood.node_tree.nodes; links=wood.node_tree.links
tex=n.new('ShaderNodeTexNoise'); tex.inputs['Scale'].default_value=4.5; tex.inputs['Detail'].default_value=2
coord=n.new('ShaderNodeTexCoord'); mapping=n.new('ShaderNodeVectorMath'); mapping.operation='MULTIPLY'; mapping.inputs[1].default_value=(7,.42,5)
links.new(coord.outputs['Generated'],mapping.inputs[0]); links.new(mapping.outputs[0],tex.inputs['Vector'])
ramp=n.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].position=.18; ramp.color_ramp.elements[0].color=(.035,.008,.006,1); ramp.color_ramp.elements[1].position=.82; ramp.color_ramp.elements[1].color=(.29,.065,.026,1)
links.new(tex.outputs['Fac'],ramp.inputs['Fac']); links.new(ramp.outputs[0],n.get('Principled BSDF').inputs['Base Color'])
bump=n.new('ShaderNodeBump'); bump.inputs['Strength'].default_value=.12; bump.inputs['Distance'].default_value=.018
links.new(tex.outputs['Fac'],bump.inputs['Height']); links.new(bump.outputs[0],n.get('Principled BSDF').inputs['Normal'])

# Preserve and label the two supplied meshes.
for obj in list(bpy.data.objects):
    if obj.type=='MESH':
        move(obj); bpy.context.view_layer.objects.active=obj; obj.select_set(True)
        bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
        obj.select_set(False)
        obj['source']='User blockout; original retained in Shotgun_Blockout.blend'
        obj.data.materials.clear(); obj.data.materials.append(wood if 'Приклад' in obj.name else steel)
        if 'Приклад' in obj.name:
            # Remove the unfinished sphere and trim only the thin forward guide.
            bm=bmesh.new(); bm.from_mesh(obj.data); bm.verts.ensure_lookup_table()
            bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.index >= 1046], context='VERTS')
            bmesh.ops.bisect_plane(bm, geom=list(bm.verts)+list(bm.edges)+list(bm.faces), dist=.00001, plane_co=(0,-2.27,0), plane_no=(0,1,0), clear_outer=True, clear_inner=False)
            bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.0001)
            bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(obj.data); bm.free(); obj.data.update()
            obj.data.materials.append(gold)
            for face in obj.data.polygons:
                center=sum((obj.data.vertices[v].co for v in face.vertices),Vector())/len(face.vertices)
                if center.y > -3.03 and center.z < .12: face.material_index=1
            obj.name='Stock | original blockout'
        else: obj.name='Barrel | original blockout'


def assign(obj, mat):
    obj.data.materials.clear(); obj.data.materials.append(mat); return obj

def bevel(obj, width=.025):
    b=obj.modifiers.new('Small manufactured edge','BEVEL'); b.width=width; b.segments=1
    return obj

def mesh(name, verts, faces, mat):
    data=bpy.data.meshes.new(name); data.from_pydata(verts,[],faces); data.update()
    obj=bpy.data.objects.new(name,data); model.objects.link(obj); assign(obj,mat); return obj

def box(name, loc, size, mat, bevelwidth=.015):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc)
    o=move(bpy.context.object); o.name=name; o.dimensions=size
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    assign(o,mat)
    if bevelwidth: bevel(o,bevelwidth)
    return o

def cyl(name, loc, radius, depth, mat, vertices=12, axis='Y'):
    rot={'X':(0,pi/2,0),'Y':(pi/2,0,0),'Z':(0,0,0)}[axis]
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=radius,depth=depth,location=loc,rotation=rot)
    o=move(bpy.context.object); o.name=name; assign(o,mat); return o

def ring(name,y,z,outer,inner,length,mat,x=0,n=16):
    verts=[]
    for yy,rr in [(y-length/2,outer),(y+length/2,outer),(y-length/2,inner),(y+length/2,inner)]:
        verts += [(x+rr*cos(2*pi*i/n),yy,z+rr*sin(2*pi*i/n)) for i in range(n)]
    faces=[]
    for i in range(n):
        j=(i+1)%n
        faces.extend([(i,j,n+j,n+i),(2*n+i,3*n+i,3*n+j,2*n+j),(i,2*n+i,2*n+j,j),(n+i,n+j,3*n+j,3*n+i)])
    return mesh(name,verts,faces,mat)

def sideplate(name, outline, thickness, x, mat, bw=.015):
    count=len(outline); verts=[(x+sgn*thickness/2,y,z) for sgn in [-1,1] for y,z in outline]
    faces=[tuple(reversed(range(count))),tuple(range(count,2*count))]
    faces += [(i,(i+1)%count,(i+1)%count+count,i+count) for i in range(count)]
    o=mesh(name,verts,faces,mat)
    if bw: bevel(o,bw)
    return o

def tube(name, points, radius, mat, sides=6, closed=False):
    # A low-sided continuous tube used for trim, guard, and visible engravings.
    verts=[]
    for i,p in enumerate(points):
        a=Vector(points[(i-1)%len(points)] if closed or i else points[0])
        b=Vector(points[(i+1)%len(points)] if closed or i<len(points)-1 else points[-1])
        tangent=(b-a).normalized(); u=tangent.cross(Vector((1,0,0)))
        if u.length<.01: u=tangent.cross(Vector((0,0,1)))
        u.normalize(); v=tangent.cross(u).normalized()
        verts += [tuple(Vector(p)+radius*(cos(2*pi*j/sides)*u+sin(2*pi*j/sides)*v)) for j in range(sides)]
    faces=[]; segs=len(points) if closed else len(points)-1
    for i in range(segs):
        k=(i+1)%len(points)
        for j in range(sides): faces.append((i*sides+j,i*sides+(j+1)%sides,k*sides+(j+1)%sides,k*sides+j))
    if not closed: faces += [tuple(reversed(range(sides))),tuple((len(points)-1)*sides+j for j in range(sides))]
    return mesh(name,verts,faces,mat)

def empty(name, loc, collection=rigcol):
    o=bpy.data.objects.new(name,None); collection.objects.link(o); o.location=loc; o.empty_display_type='PLAIN_AXES'; o.empty_display_size=.32; return o

def parent_keep(o,p):
    bpy.context.view_layer.update()
    world=o.matrix_world.copy(); o.parent=p; o.matrix_world=world

def screw(name,x,y,z):
    o=cyl(name,(x,y,z),.055,.028,edge,8,'X')
    box(name+' | slot',(x+(.016 if x>0 else -.016),y,z),(.012,.058,.012),black,0)
    return o

# Receiver with an open side window around the cylinder.
for s in [-1,1]:
    x=s*.33
    sideplate('Receiver | rear cheek', [(-2.21,.05),(-2.28,.68),(-2.05,.91),(-1.82,.91),(-1.82,.02)],.11,x,gold)
    sideplate('Receiver | front cheek',[(-.67,.0),(-.67,.95),(-.31,.94),(-.1,.72),(-.25,.03)],.11,x,gold)
    sideplate('Receiver | lower rail',[(-2.2,.03),(-1.9,-.1),(-.45,-.02),(-.21,.12),(-.28,.23),(-2.17,.18)],.09,x,gold)
    sideplate('Receiver | top rail',[(-2.13,.94),(-.5,.94),(-.29,.85),(-.28,.75),(-2.12,.79)],.09,x,gold)
    tube('Receiver | light border',[(s*.395,y,z) for y,z in [(-2.15,.17),(-1.87,.05),(-.47,.11),(-.3,.22)]],.014,bright)
    for yy,zz in [(-2.05,.65),(-1.99,.26),(-.47,.67),(-.48,.28)]: screw('Receiver | slotted fastener',s*.402,yy,zz)
    # Winding leaves in the front corner, simplified from the gold concept.
    tube('Receiver | scroll',[(s*.4,y,z) for y,z in [(-.58,.84),(-.39,.78),(-.49,.64),(-.63,.57),(-.5,.43),(-.33,.51)]],.018,bright)
    cyl('Receiver | enamel pin',(s*.428,-.44,.58),.079,.035,gold,10,'X')
    cyl('Receiver | turquoise pin',(s*.453,-.44,.58),.052,.036,gem,8,'X')

# Low-poly six-flute rotating cylinder. Flutes are in its silhouette, not textures.
cy=-1.26; cz=.49; n=48; verts=[]
for yy in [cy-.57,cy+.57]:
    for i in range(n):
        a=2*pi*i/n; r=.443 if i%8 in [2,3,4,5] else .486
        verts.append((r*cos(a),yy,cz+r*sin(a)))
faces=[tuple(reversed(range(n))),tuple(range(n,n*2))]
faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
drum=mesh('Cylinder | six fluted chambers',verts,faces,steel)
drumcontrol=empty('CTRL | cylinder', (0,cy,cz))
parent_keep(drum,drumcontrol)
for yy in [cy-.58,cy+.58]:
    o=ring('Cylinder | rim',yy,cz,.486,.42,.065,edge,n=24); parent_keep(o,drumcontrol)
    o=ring('Cylinder | brass line',yy,cz,.491,.478,.018,gold,n=24); parent_keep(o,drumcontrol)
# Dark chamber mouths visible around the front face; purely visual prop geometry.
for i in range(6):
    a=2*pi*i/6
    o=cyl('Cylinder | chamber recess',(.302*cos(a),cy+.585,cz+.302*sin(a)),.097,.012,black,10)
    parent_keep(o,drumcontrol)

# Underbarrel tube and short ribbed wood/leather fore-end.
cyl('Underbarrel | tube',(0,1.8,.12),.105,4.1,steel,12)
cyl('Underbarrel | end cap',(0,3.88,.12),.13,.1,gold,12)
pumpcontrol=empty('CTRL | fore-end',(0,.62,.16))
fore=cyl('Fore-end | oxblood grip',(0,.68,.14),.205,1.34,leather,12); parent_keep(fore,pumpcontrol)
for yy in [.07,.25,.43,.61,.79,.97,1.15,1.31]:
    o=ring('Fore-end | wrap',yy,.14,.212,.196,.035,wood,n=12); parent_keep(o,pumpcontrol)
for yy in [-.02,1.39]:
    o=ring('Fore-end | brass ferrule',yy,.14,.22,.11,.095,gold,n=12); parent_keep(o,pumpcontrol)

# Hollow muzzle extension covers the original closed end without destructive edits.
for s in [-1,1]:
    x=s*.2
    ring('Muzzle | crown',4.59,.675505,.224,.161,.26,gold,x=x,n=16)
    ring('Muzzle | dark bore',4.52,.675505,.160,.147,.46,black,x=x,n=16)
    cyl('Muzzle | bore shadow',(x,4.32,.675505),.147,.01,black,16)
    ring('Muzzle | rim highlight',4.729,.675505,.224,.161,.027,edge,x=x,n=16)
    for yy in [1.45,3.05]:
        ring('Barrel | brass band',yy,.675505,.217,.20,.10,gold,x=x,n=16)
for yy in [1.45,3.05]:
    box('Barrel | band saddle',(0,yy,.35),(.25,.08,.33),gold,.015)
# Raised sights and long top rib.
box('Barrel | sight rib',(0,1.84,.906),(.07,5.38,.045),edge,.008)
sideplate('Front sight',[ (4.29,.91),(4.46,.91),(4.39,1.1),(4.32,1.1)],.08,0,gold,.006)
box('Rear sight | base',(0,-.37,.99),(.3,.19,.07),steel,.01)
for s in [-1,1]: box('Rear sight | notch',(s*.095,-.37,1.06),(.055,.12,.1),gold,.008)

# Trigger guard, trigger, and a cocking hammer. Each moving piece has its own pivot.
guardpath=[(0,-2.34,.03),(0,-2.39,-.23),(0,-2.27,-.45),(0,-2.03,-.52),(0,-1.75,-.50),(0,-1.55,-.35),(0,-1.51,-.08)]
tube('Trigger | brass guard',guardpath,.047,gold,8)
triggercontrol=empty('CTRL | trigger',(0,-1.93,.08))
trig=sideplate('Trigger | curved blade',[(-2.0,.08),(-1.92,.08),(-1.94,-.16),(-1.86,-.26),(-1.94,-.3),(-2.04,-.18)],.09,0,edge,.008)
parent_keep(trig,triggercontrol)
hammercontrol=empty('CTRL | hammer',(0,-2.12,.72))
hammer=sideplate('Hammer | cocking spur',[(-2.26,.64),(-2.04,.69),(-2.04,.98),(-2.21,1.18),(-2.46,1.27),(-2.37,1.08),(-2.21,1.01)],.15,0,steel,.015)
parent_keep(hammer,hammercontrol)
for yy,zz in [(-2.23,1.145),(-2.31,1.185),(-2.39,1.22)]:
    o=box('Hammer | grip serration',(0,yy,zz),(.17,.035,.025),gold,.004); parent_keep(o,hammercontrol)
for s in [-1,1]: cyl('Hammer | axle',(s*.105,-2.12,.72),.105,.03,gold,10,'X')

# Antique brass stock edging and restrained geometric inlays.
for s in [-1,1]:
    # Coordinates follow the supplied silhouette rather than replacing the stock.
    outline=[(-5.39,-1.11),(-5.39,.11),(-4.67,.25),(-3.46,.42),(-2.77,.39),(-2.38,.56),(-2.32,.31),(-3.06,.06)]
    # Keep inlays on the broad, visible rear portion of the stock.
    sideplate('Stock | heel plate',[(-5.5,-1.18),(-5.5,.18),(-5.32,.21),(-5.3,-1.1)],.045,s*.302,gold,.018)
    tube('Stock | heel trim',[(s*.335,-5.37,-1.05),(s*.335,-5.38,.10),(s*.335,-4.72,.23)],.024,bright)
    sideplate('Stock | diamond escutcheon',[(-4.88,-.04),(-4.47,.17),(-4.05,.03),(-4.47,-.19)],.025,s*.332,gold,.009)
    sideplate('Stock | diamond inset',[(-4.73,-.04),(-4.47,.09),(-4.21,.015),(-4.47,-.12)],.028,s*.351,steel,.004)
    sideplate('Stock | central turquoise',[(-4.55,-.025),(-4.47,.035),(-4.39,-.025),(-4.47,-.08)],.03,s*.372,gem,.003)
    tube('Stock | upper scroll',[(s*.32,y,z) for y,z in [(-5.24,.03),(-5.07,.11),(-4.93,.07),(-4.85,.14)]],.018,bright)
    tube('Stock | lower scroll',[(s*.32,y,z) for y,z in [(-5.23,-.85),(-5.11,-.62),(-4.94,-.52),(-5.0,-.39),(-5.16,-.41)]],.019,bright)
    screw('Stock | heel rivet',s*.345,-5.39,.03)
    screw('Stock | heel rivet',s*.345,-5.39,-.99)
# Metal butt pad and receiver wrist collar.
sideplate('Stock | butt pad',[(-5.57,-1.22),(-5.57,.16),(-5.48,.19),(-5.46,-1.18)],.64,0,steel,.025)
sideplate('Stock | wrist collar',[(-2.75,.34),(-2.69,.53),(-2.43,.68),(-2.27,.35),(-2.44,.24)],.48,0,gold,.012)

# Rigid hierarchy; no skinning required for a mechanical low-poly prop.
root=empty('CTRL | recoil / whole prop',(0,-2.0,.4))
root['usage']='Animate this control for whole-prop motion; cylinder, hammer, trigger and fore-end are separate children.'
for obj in list(model.objects):
    if obj.parent is None: parent_keep(obj,root)
for obj in [drumcontrol,pumpcontrol,triggercontrol,hammercontrol]: parent_keep(obj,root)

# 96 frames / 24 fps: readable anticipation, two stylized mechanism cycles, settle.
scene.frame_start=1; scene.frame_end=96; scene.render.fps=24
for a,b in [('READY',1),('COCK',14),('RELEASE',23),('INDEX',38),('COCK 2',54),('RELEASE 2',63),('SETTLE',84)]: scene.timeline_markers.new(a,frame=b)
rootbase=root.location.copy()
for f,dy,rx in [(1,0,0),(18,0,0),(23,-.27,.065),(28,-.08,.018),(36,0,0),(58,0,0),(63,-.27,.065),(68,-.08,.018),(78,0,0),(96,0,0)]:
    root.location=rootbase+Vector((0,dy,0)); root.rotation_euler=(rx,0,0)
    root.keyframe_insert(data_path='location',frame=f); root.keyframe_insert(data_path='rotation_euler',frame=f)
for f,a in [(1,0),(8,0),(18,.6),(21,.6),(23,-.12),(27,0),(48,0),(58,.6),(61,.6),(63,-.12),(67,0),(96,0)]:
    hammercontrol.rotation_euler[0]=a; hammercontrol.keyframe_insert(data_path='rotation_euler',frame=f)
for f,a in [(1,0),(20,0),(23,-.28),(29,0),(60,0),(63,-.28),(69,0),(96,0)]:
    triggercontrol.rotation_euler[0]=a; triggercontrol.keyframe_insert(data_path='rotation_euler',frame=f)
for f,a in [(1,0),(28,0),(40,pi/3),(68,pi/3),(80,2*pi/3),(96,2*pi/3)]:
    drumcontrol.rotation_euler[1]=a; drumcontrol.keyframe_insert(data_path='rotation_euler',frame=f)
base=pumpcontrol.location.copy()
for f,d in [(1,0),(28,0),(34,-.34),(42,0),(68,0),(74,-.34),(82,0),(96,0)]:
    pumpcontrol.location=base+Vector((0,d,0)); pumpcontrol.keyframe_insert(data_path='location',frame=f)
# Smooth mechanical transitions; no automatic cycle modifier or drifting reset.
for obj in [root,hammercontrol,triggercontrol,drumcontrol,pumpcontrol]:
    action=obj.animation_data.action
    action.name='Shotgun | '+obj.name.removeprefix('CTRL | ')
    for slot in action.slots:
        for layer in action.layers:
            for strip in layer.strips:
                try: curves=strip.channelbag(slot).fcurves
                except (AttributeError,RuntimeError): continue
                for fc in curves:
                    for k in fc.keyframe_points: k.interpolation='BEZIER'; k.handle_left_type='AUTO_CLAMPED'; k.handle_right_type='AUTO_CLAMPED'
scene.frame_set(1)

# Relink all three supplied references and pack them into the final project.
for i, path in enumerate(sorted((ROOT/'Shotgun_Animation_Kit').glob('*.jpg'))):
    im=bpy.data.images.load(str(path),check_existing=True); im.pack()
    o=bpy.data.objects.new('Reference | '+path.stem,None); refs.objects.link(o); o.empty_display_type='IMAGE'; o.data=im; o.empty_display_size=10
    o.location=(3+i*3,0,-4); o.hide_render=True; o.hide_set(True)
for im in list(bpy.data.images):
    if im.users==0: bpy.data.images.remove(im)

# Dark, restrained studio presentation. Geometry remains separate from the studio.
world=bpy.data.worlds.new('Studio | charcoal')
world.use_nodes=True; world.node_tree.nodes['Background'].inputs[0].default_value=(.045,.06,.075,1); world.node_tree.nodes['Background'].inputs[1].default_value=.4
scene.world=world
floor=material('Studio | floor',(.018,.025,.033),.08,.5)
box('Studio | plinth',(0,-.3,-1.68),(200,200,.1),floor,0); move(bpy.context.object,studio)

def camera(name, pos, target, ortho):
    data=bpy.data.cameras.new(name); o=bpy.data.objects.new(name,data); studio.objects.link(o); o.location=pos
    o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler(); data.type='ORTHO'; data.ortho_scale=ortho; data.lens=55
    return o
hero=camera('Camera | hero',(11.8,8.2,6.7),(0,-.35,.0),12.7)
side=camera('Camera | side',(14,-.5,3.2),(0,-.5,.0),12)
detail=camera('Camera | mechanism',(6,-.1,3.1),(0,-1.24,.38),4.2)
scene.camera=hero

def light(name, pos, energy, size, color, target=(0,0,0)):
    d=bpy.data.lights.new(name,'AREA'); d.energy=energy; d.shape='DISK'; d.size=size; d.color=color
    o=bpy.data.objects.new(name,d); studio.objects.link(o); o.location=pos; o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler()
light('Key | warm softbox',(5,-1,8),1900,7,(1,.82,.64),(0,-1,0))
light('Fill | cool softbox',(3,6,3),1100,6,(.62,.79,1))
light('Rim | strip',(-4,-1,5),2300,5,(.65,.85,1))
light('Stock | softbox',(2,-7,3),700,4,(1,.75,.5),(0,-4,0))
scene.render.engine='CYCLES'; scene.cycles.device='CPU'; scene.cycles.samples=40; scene.cycles.use_denoising=True
scene.render.threads_mode='FIXED'; scene.render.threads=5
scene.render.resolution_x=1440; scene.render.resolution_y=900; scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'; scene.render.film_transparent=False
scene.view_settings.view_transform='AgX'
scene.render.filepath='//previews/Shotgun_Hero.png'
scene.render.use_file_extension=True
# Clean opening state with the finished prop framed in material view.
bpy.ops.object.select_all(action='DESELECT'); root.select_set(True); bpy.context.view_layer.objects.active=root
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.shading.type='MATERIAL'; area.spaces.active.clip_end=1000
            area.spaces.active.region_3d.view_distance=13
            area.spaces.active.region_3d.view_location=Vector((0,-.4,.15))
            area.spaces.active.region_3d.view_rotation=hero.rotation_euler.to_quaternion()
scene['Asset']='Fantasy low-poly double-barrel revolving shotgun; visual game prop'
scene['Animation']='Frames 1–96 at 24 fps. Two cock / release / recoil / index cycles.'
scene['Source']='Two original meshes preserved; reference images packed. No external textures.'
scene['Controls']='CTRL | recoil / whole prop; CTRL | cylinder; CTRL | hammer; CTRL | trigger; CTRL | fore-end'
bpy.context.preferences.filepaths.save_version=0
bpy.context.preferences.filepaths.file_preview_type='NONE'
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Shotgun.blend'),compress=True)
print('SAVED_FINISHED',ROOT/'Shotgun.blend',flush=True)
if os.environ.get('SHOTGUN_RENDER')=='1':
    scene.render.filepath=str(ROOT/'previews'/'Shotgun_Hero.png'); bpy.ops.render.render(write_still=True)
    scene.camera=side; scene.render.filepath=str(ROOT/'previews'/'Shotgun_Side.png'); bpy.ops.render.render(write_still=True)
    scene.camera=detail; scene.render.resolution_x=1000; scene.render.resolution_y=800
    scene.render.filepath=str(ROOT/'previews'/'Shotgun_Detail.png'); bpy.ops.render.render(write_still=True)
