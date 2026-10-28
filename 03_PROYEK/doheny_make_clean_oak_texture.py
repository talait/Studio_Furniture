import bpy, numpy as np
src=bpy.data.images.load(r"C:/Users/Staff/Downloads/DOHENY/textures/oak_plank_terapan.png")
w,h=src.size; c=src.channels
a=np.array(src.pixels[:],dtype=np.float32).reshape(h,w,c)[:,:,:3]
a=a[:, 40:w-12]                      # buang tepi gelap kiri/kanan
H,W,_=a.shape
def box(x,r,axis):
    pad=[(0,0)]*x.ndim; pad[axis]=(r,r)
    p=np.pad(x,pad,mode='reflect'); cs=np.cumsum(p,axis=axis,dtype=np.float64)
    cs=np.insert(cs,0,0,axis=axis)
    hi=np.take(cs,np.arange(2*r+1,2*r+1+x.shape[axis]),axis=axis)
    lo=np.take(cs,np.arange(0,x.shape[axis]),axis=axis)
    return (hi-lo)/(2*r+1)
L=a.mean(2)
blur=L
for _ in range(3): blur=box(box(blur,40,1),12,0)   # tone besar (bercak/ujung gelap)
gain=(L.mean()/np.maximum(blur,1e-3))[:,:,None]
out=np.clip(a*gain,0,1)
# warna rata-rata dikunci ke rata-rata tekstur asli bagian tengah (seperti lengan atas)
out=out*(a.reshape(-1,3).mean(0)/out.reshape(-1,3).mean(0))
L2=out.mean(2); print('##clean',W,H,'mean',round(float(L2.mean()),3),'min',round(float(L2.min()),3),'colmin',round(float(L2.mean(0).min()),3),'colmax',round(float(L2.mean(0).max()),3))
img=bpy.data.images.new('oak_clean',W,H,alpha=False)
rgba=np.concatenate([out,np.ones((H,W,1),np.float32)],2)
img.pixels.foreach_set(rgba.astype(np.float32).ravel())
img.filepath_raw=r"C:/Users/Staff/Downloads/DOHENY/textures/oak_plank_bersih.png"; img.file_format='PNG'; img.save()
print('##saved')
