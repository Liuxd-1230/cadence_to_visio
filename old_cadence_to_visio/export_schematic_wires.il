; Export schematic wire geometry from the current Virtuoso schematic cellView.
; Usage in CIW:
;   load("/path/to/export_schematic_wires.il")
;   exportSchematicWires("/path/to/wires.tsv")

procedure( c2vPointX(pt)
  car(pt)
)

procedure( c2vPointY(pt)
  cadr(pt)
)

procedure( c2vNetName(fig fallbackName)
  let( (net)
    net = fig~>net
    if(net && net~>name then
      net~>name
    else
      fallbackName
    )
  )
)

procedure( c2vWritePointSegments(fp fig fallbackName groupId)
  let( (pts p1 p2 i count netName objType layerName purpose)
    count = 0
    objType = fig~>objType
    layerName = fig~>layerName
    purpose = fig~>purpose
    netName = c2vNetName(fig fallbackName)

    when(or(equal(objType "line") equal(objType "path"))
      pts = fig~>points
      when(pts && length(pts) >= 2
        for(i 0 length(pts)-2
          p1 = nth(i pts)
          p2 = nth(i+1 pts)
          count = count + 1
          fprintf(fp "%d\t%d\t%s\t%s\t%s\t%s\t%g\t%g\t%g\t%g\n"
            groupId count netName objType layerName purpose
            c2vPointX(p1) c2vPointY(p1) c2vPointX(p2) c2vPointY(p2)
          )
        )
      )
    )

    when(equal(objType "pathSeg")
      p1 = fig~>beginPt
      p2 = fig~>endPt
      when(p1 && p2
        count = 1
        fprintf(fp "%d\t%d\t%s\t%s\t%s\t%s\t%g\t%g\t%g\t%g\n"
          groupId count netName objType layerName purpose
          c2vPointX(p1) c2vPointY(p1) c2vPointX(p2) c2vPointY(p2)
        )
      )
    )
    count
  )
)

procedure( exportSchematicWires(outFile)
  let( (cv fp net fig total groupId count netName)
    cv = geGetEditCellView()
    unless(cv
      error("No editable schematic cellView is active.\n")
    )

    fp = outfile(outFile "w")
    fprintf(fp "group_id\tseg_id\tnet\tobj_type\tlayer\tpurpose\tx1\ty1\tx2\ty2\n")

    total = 0
    groupId = 0

    foreach(net cv~>nets
      netName = net~>name
      foreach(fig net~>figs
        when(member(fig~>objType list("line" "path" "pathSeg"))
          when(equal(fig~>layerName "wire")
            groupId = groupId + 1
            count = c2vWritePointSegments(fp fig netName groupId)
            total = total + count
          )
        )
      )
    )

    close(fp)
    printf("Exported %d wire segments to %s\n" total outFile)
  )
)
