; Minimal Virtuoso schematic wire-line exporter.
; This version only uses the object model already verified in CIW:
;   obj~>objType  => "line"
;   obj~>layerName => "wire"
;   obj~>points   => ((x1 y1) (x2 y2) ...)
;
; Usage in CIW:
;   load("/path/to/export_wire_lines_only.il")
;   exportWireLinesOnly("/path/to/wires.tsv")

procedure( exportWireLinesOnly(outFile)
  let( (cv fp net fig pts p1 p2 i lastIdx groupId segId total netName)
    cv = geGetEditCellView()
    unless(cv
      error("No editable schematic cellView is active.\n")
    )

    fp = outfile(outFile "w")
    fprintf(fp "group_id\tseg_id\tnet\tobj_type\tlayer\tpurpose\tx1\ty1\tx2\ty2\n")

    groupId = 0
    total = 0

    foreach(net cv~>nets
      netName = net~>name

      foreach(fig net~>figs
        when(equal(fig~>objType "line")
          when(equal(fig~>layerName "wire")
            pts = fig~>points

            when(pts
              when(length(pts) >= 2
                groupId = groupId + 1
                segId = 0
                lastIdx = length(pts) - 2

                for(i 0 lastIdx
                  p1 = nth(i pts)
                  p2 = nth(i + 1 pts)
                  segId = segId + 1
                  total = total + 1

                  fprintf(fp "%d\t%d\t%s\t%s\t%s\t%s\t%g\t%g\t%g\t%g\n"
                    groupId
                    segId
                    netName
                    fig~>objType
                    fig~>layerName
                    fig~>purpose
                    car(p1)
                    cadr(p1)
                    car(p2)
                    cadr(p2)
                  )
                )
              )
            )
          )
        )
      )
    )

    close(fp)
    printf("Exported %d wire line segments to %s\n" total outFile)
  )
)

