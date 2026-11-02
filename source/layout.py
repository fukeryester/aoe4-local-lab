"""Separate overlapping labels while keeping a leader at each entity's position."""
def arrange(labels,font_size,width,height):
    grid={};result=[];cell=64
    def cells(box):
        left,top,right,bottom=box
        for x in range(int(left)//cell,int(right)//cell+1):
            for y in range(int(top)//cell,int(bottom)//cell+1):yield x,y
    def overlaps(a,b):return a[0]<b[2] and a[2]>b[0] and a[1]<b[3] and a[3]>b[1]
    for uid,x,y,text,color in sorted(labels,key=lambda item:(item[2],item[0])):
        tw=min(width-8,max(22,sum(font_size if ord(c)>255 else font_size*.63 for c in text)+8));th=font_size+5
        chosen=None
        for step in range(20):
            dx=0 if step<10 else ((step%2)*2-1)*(tw+12)
            dy=18+(step if step<10 else (step-10)//2)*(th+4)
            tx=max(tw/2+2,min(width-tw/2-2,x+dx));ty=max(th+2,min(height-4,y-dy))
            box=(tx-tw/2,ty-th,tx+tw/2,ty+3)
            if not any(overlaps(box,b) for key in cells(box) for b in grid.get(key,())):
                chosen=(tx,ty,box);break
        if chosen is None:
            tx=max(tw/2+2,min(width-tw/2-2,x));ty=max(th+2,y-18);box=(tx-tw/2,ty-th,tx+tw/2,ty+3);chosen=(tx,ty,box)
        tx,ty,box=chosen
        for key in cells(box):grid.setdefault(key,[]).append(box)
        result.append((uid,x,y,tx,ty,text,color))
    return result
