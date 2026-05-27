; Export instance name, cell, XY, orient, and BBox from the current schematic.
;
; Usage in CIW:
;   load("/home/wzzheng/worklib/skills/export_inst_xy_orient.il")
;   exportInstXYOrient(geGetEditCellView() "/home/wzzheng/worklib/skills/inst_info.txt")
;
; Convenience wrapper:
;   c2vExportInstXYOrient("/home/wzzheng/worklib/skills/inst_info.txt")

procedure( exportInstXYOrient(cv outFile)
  let( (fp inst)
    unless(cv
      error("No schematic cellView was provided.\n")
    )
    fp = outfile(outFile "w")
    foreach(inst cv~>instances
      fprintf(fp "Name: %s  Cell: %s\n" inst~>name inst~>cellName)
      fprintf(fp "  XY: %L\n" inst~>xy)
      fprintf(fp "  Orient: %s\n" inst~>orient)
      fprintf(fp "  BBox: %L\n\n" inst~>bBox)
    )
    close(fp)
    printf("Exported instance XY/orient/BBox to %s\n" outFile)
  )
)

procedure( c2vExportInstXYOrient(outFile)
  exportInstXYOrient(geGetEditCellView() outFile)
)
