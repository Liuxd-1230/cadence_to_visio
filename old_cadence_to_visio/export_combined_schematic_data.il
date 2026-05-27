; Combined Cadence Virtuoso schematic exporter for cadence_to_visio.
;
; It writes one text file containing:
;   1. CDL-like netlist/connectivity
;   2. instance XY/orient/BBox information
;   3. verified wire line coordinates
;
; Basic usage in CIW:
;   load("/home/wzzheng/worklib/skills/export_combined_schematic_data.il")
;   c2vExportAllTxt("/home/wzzheng/worklib/skills/c2v_export.txt")
;
; If you already exported exact CDL using Virtuoso's CDL netlister:
;   c2vExportAllTxtWithCdlFile(
;     "/home/wzzheng/worklib/skills/c2v_export.txt"
;     "/home/wzzheng/worklib/skills/netlist.txt"
;   )

procedure( c2vPointX(pt)
  car(pt)
)

procedure( c2vPointY(pt)
  cadr(pt)
)

procedure( c2vWriteBanner(fp title)
  fprintf(fp "\n")
  fprintf(fp "################################################################\n")
  fprintf(fp "# %s\n" title)
  fprintf(fp "################################################################\n")
)

procedure( c2vNetNameFromInstTerm(instTerm)
  let( (net)
    net = instTerm~>net
    if(net then
      if(net~>name then
        net~>name
      else
        "UNCONNECTED"
      )
    else
      "UNCONNECTED"
    )
  )
)

procedure( c2vTermNameFromInstTerm(instTerm)
  let( (term)
    term = instTerm~>term
    if(term then
      if(term~>name then
        term~>name
      else
        "UNKNOWN_TERM"
      )
    else
      "UNKNOWN_TERM"
    )
  )
)

procedure( c2vWriteCdlLikeNetlist(fp cv)
  let( (inst instTerm term termName netName)
    c2vWriteBanner(fp "BEGIN_NETLIST")
    fprintf(fp "* CDL-like connectivity generated from the open schematic database.\n")
    fprintf(fp "* For exact PDK/CDL parameters, merge a CDL file with c2vExportAllTxtWithCdlFile().\n")
    fprintf(fp "* Library Name: %s\n" cv~>libName)
    fprintf(fp "* Cell Name:    %s\n" cv~>cellName)
    fprintf(fp "* View Name:    %s\n" cv~>viewName)
    fprintf(fp "\n")

    fprintf(fp ".SUBCKT %s" cv~>cellName)
    foreach(term cv~>terminals
      fprintf(fp " %s" term~>name)
    )
    fprintf(fp "\n")

    foreach(inst cv~>instances
      fprintf(fp "* PIN_ORDER %s" inst~>name)
      foreach(instTerm inst~>instTerms
        termName = c2vTermNameFromInstTerm(instTerm)
        fprintf(fp " %s" termName)
      )
      fprintf(fp "\n")

      fprintf(fp "X%s" inst~>name)
      foreach(instTerm inst~>instTerms
        netName = c2vNetNameFromInstTerm(instTerm)
        fprintf(fp " %s" netName)
      )
      fprintf(fp " %s\n" inst~>cellName)
    )

    fprintf(fp ".ENDS %s\n" cv~>cellName)
    fprintf(fp "# END_NETLIST\n")
  )
)

procedure( c2vCopyFileIntoSection(fp fileName title)
  let( (in line)
    c2vWriteBanner(fp title)
    in = infile(fileName)
    if(in then
      line = gets(in)
      while(line
        fprintf(fp "%s" line)
        line = gets(in)
      )
      close(in)
    else
      fprintf(fp "* ERROR: could not open CDL file: %s\n" fileName)
    )
    if(equal(title "BEGIN_NETLIST") then
      fprintf(fp "\n# END_NETLIST\n")
    else
      fprintf(fp "\n# END_%s\n" title)
    )
  )
)

procedure( c2vWriteInstXYOrient(fp cv)
  let( (inst)
    c2vWriteBanner(fp "BEGIN_INSTANCES")
    foreach(inst cv~>instances
      fprintf(fp "Name: %s  Cell: %s\n" inst~>name inst~>cellName)
      fprintf(fp "  XY: %L\n" inst~>xy)
      fprintf(fp "  Orient: %s\n" inst~>orient)
      fprintf(fp "  BBox: %L\n\n" inst~>bBox)
    )
    fprintf(fp "# END_INSTANCES\n")
  )
)

procedure( c2vWriteWireLines(fp cv)
  let( (net fig pts p1 p2 i nextIdx lastIdx groupId segId total netName)
    c2vWriteBanner(fp "BEGIN_WIRES")
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

    fprintf(fp "# END_WIRES\n")
    fprintf(fp "# WIRE_SEGMENT_COUNT %d\n" total)
    total
  )
)

procedure( c2vWriteHeader(fp cv)
  fprintf(fp "# C2V_COMBINED_EXPORT_V1\n")
  fprintf(fp "# Library: %s\n" cv~>libName)
  fprintf(fp "# Cell:    %s\n" cv~>cellName)
  fprintf(fp "# View:    %s\n" cv~>viewName)
)

procedure( c2vExportAllTxt(outFile)
  let( (cv fp total)
    cv = geGetEditCellView()
    unless(cv
      error("No editable schematic cellView is active.\n")
    )

    fp = outfile(outFile "w")
    c2vWriteHeader(fp cv)
    c2vWriteCdlLikeNetlist(fp cv)
    c2vWriteInstXYOrient(fp cv)
    total = c2vWriteWireLines(fp cv)
    close(fp)
    printf("Exported combined schematic data to %s\n" outFile)
    printf("Exported %d wire line segments\n" total)
  )
)

procedure( c2vExportAllTxtWithCdlFile(outFile cdlFile)
  let( (cv fp total)
    cv = geGetEditCellView()
    unless(cv
      error("No editable schematic cellView is active.\n")
    )

    fp = outfile(outFile "w")
    c2vWriteHeader(fp cv)
    c2vCopyFileIntoSection(fp cdlFile "BEGIN_NETLIST")
    c2vWriteInstXYOrient(fp cv)
    total = c2vWriteWireLines(fp cv)
    close(fp)
    printf("Exported combined schematic data to %s\n" outFile)
    printf("Merged CDL netlist from %s\n" cdlFile)
    printf("Exported %d wire line segments\n" total)
  )
)
