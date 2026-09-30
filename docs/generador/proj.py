import json
def write_pro(path, name):
    def nc(n,clr,w,vd=0.6,vdr=0.3):
        return {"name":n,"clearance":clr,"track_width":w,"via_diameter":vd,"via_drill":vdr,"microvia_diameter":0.3,"microvia_drill":0.1,
                "diff_pair_gap":0.25,"diff_pair_via_gap":0.25,"diff_pair_width":0.2,"line_style":0,"pcb_color":"rgba(0, 0, 0, 0.000)",
                "schematic_color":"rgba(0, 0, 0, 0.000)","wire_width":6,"bus_width":12}
    pro={
     "board":{"design_settings":{"defaults":{"board_outline_line_width":0.1,"copper_line_width":0.2,"copper_text_size_h":1.5,"copper_text_size_v":1.5,"copper_text_thickness":0.3,"silk_line_width":0.15,"silk_text_size_h":1.0,"silk_text_size_v":1.0,"silk_text_thickness":0.15},
       "rules":{"min_clearance":0.2,"min_track_width":0.2,"min_via_diameter":0.5,"min_through_hole_diameter":0.3,"min_hole_to_hole":0.25,"min_copper_edge_clearance":0.4,"min_hole_clearance":0.25,"min_silk_clearance":0.0,"solder_mask_to_copper_clearance":0.0,"min_text_height":0.8,"min_text_thickness":0.08,"min_microvia_diameter":0.2,"min_microvia_drill":0.1,"min_resolve_spokes":2,"max_error":0.005,"allow_blind_buried_vias":False,"allow_microvias":False,"use_height_for_length_calcs":True},
       "track_widths":[0.0,0.25,0.4,0.6,1.0,2.5],"via_dimensions":[{"diameter":0.0,"drill":0.0},{"diameter":0.6,"drill":0.3}]}},
     "meta":{"filename":name+".kicad_pro","version":1},
     "net_settings":{"classes":[nc("Default",0.2,0.25),nc("PWR",0.2,0.6),nc("MAINS",2.0,1.0,1.6,0.8)],
       "meta":{"version":3},
       "netclass_patterns":[{"netclass":"PWR","pattern":p} for p in ["GND","+5V","+3V3","COIL_N"]]+[{"netclass":"MAINS","pattern":p} for p in ["L_IN","L_OUT","N","L_F"]]},
     "schematic":{"legacy_lib_dir":"","legacy_lib_list":[]},
     "sheets":[], "text_variables":{}
    }
    json.dump(pro,open(path,'w'),indent=2)
DRU='''(version 1)
(rule "Red 230V a baja tension"
  (constraint clearance (min 4mm))
  (condition "A.NetClass == 'MAINS' && B.NetClass != 'MAINS'"))
(rule "Pistas de red entre si"
  (constraint clearance (min 2mm))
  (condition "A.NetClass == 'MAINS' && B.NetClass == 'MAINS'"))
(rule "Geometria interna del rele (COM entre bobinas)"
  (constraint clearance (min 2mm))
  (condition "A.intersectsCourtyard('K1') && B.intersectsCourtyard('K1')"))
'''
