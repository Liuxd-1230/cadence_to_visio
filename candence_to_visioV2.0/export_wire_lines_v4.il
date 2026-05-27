; Export only verified Virtuoso schematic wire line objects.
; This script intentionally avoids cond/or/member/path/pathSeg compatibility logic.
;
; Usage in CIW:
;   load("/home/wzzheng/worklib/skills/export_wire_lines_v4.il")
;   c2vExportWireLinesV4("/home/wzzheng/worklib/skills/wires.tsv")

procedure( c2vExportWireLinesV4(outFile)
  let( (cv fp net fig pts p1 p2 i nextIdx lastIdx groupId segId total netName)
    cv = geGetEditCellView()

    fp = outfile(outFile "w")
    fprintf(fp "group_id\tseg_id\tnet\tobj_type\tlayer\tpurpose\tx1\ty1\tx2\ty2\n")

    groupId = 0
    total = 0

    foreach(net cv~>nets
      netName = net~>name

      foreach(fig net~>figs
        if(equal(fig~>objType "line") then
          if(equal(fig~>layerName "wire") then
            pts = fig~>points

            if(pts then
              if(length(pts) >= 2 then
                groupId = groupId + 1
                segId = 0
                lastIdx = length(pts) - 2

                for(i 0 lastIdx
                  nextIdx = i + 1
                  p1 = nth(i pts)
                  p2 = nth(nextIdx pts)
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
