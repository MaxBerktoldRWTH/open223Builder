from open223Builder.ontology.namespaces import S223, QUDTU, QUDTQK


svg_library = {
    S223.Junction: """
    <svg width="20" height="20" xmlns="http://www.w3.org/2000/svg">
        <circle cx="10" cy="10" r="10" fill="white" stroke="black" stroke-width="1"/>
    </svg>
    """,
    S223.Valve: """
        <svg width="50" height="50" xmlns="http://www.w3.org/2000/svg">
          <path d="M 0, 10 L 0, 40 L 25, 25 Z" fill="white" stroke="black" stroke-width="1"/>
          <path d="M 50, 10 L 50, 40 L 25, 25 Z" fill="white" stroke="black" stroke-width="1"/>
        </svg>
    """,
    S223.TwoWayValve: """
        <svg width="50" height="50" xmlns="http://www.w3.org/2000/svg">
          <path d="M 0, 10 L 0, 40 L 25, 25 Z" fill="white" stroke="black" stroke-width="1"/>
          <path d="M 50, 10 L 50, 40 L 25, 25 Z" fill="white" stroke="black" stroke-width="1"/>
        </svg>
    """,
    S223.ThreeWayValve: """
        <svg width="50" height="50" xmlns="http://www.w3.org/2000/svg">
            <path d="M 0, 10 L 0, 40 L 25, 25 Z" fill="white" stroke="black" stroke-width="1"/>
            <path d="M 50, 10 L 50, 40 L 25, 25 Z" fill="white" stroke="black" stroke-width="1"/>
            <path d="M 10, 50 L 40, 50 L 25, 25 Z" fill="white" stroke="black" stroke-width="1"/>
        </svg>
    """,
    S223.Pump: """
        <svg width="50" height="50" xmlns="http://www.w3.org/2000/svg">
            <circle cx="25" cy="25" r="25" fill="white" stroke="black" stroke-width="1"/>
            <path d="M 25 0 L 50 25" stroke="black" stroke-width="1" fill="white"/>
            <path d="M 25 50 L 50 25" stroke="black" stroke-width="1" fill="white"/>
        </svg>
    """,
    S223.Boiler: """
        <svg
           width="50"
           height="80"
           version="1.1"
           id="svg2"
           sodipodi:docname="boiler.svg"
           inkscape:version="1.4 (86a8ad7, 2024-10-11)"
           xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
           xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
           xmlns="http://www.w3.org/2000/svg"
           xmlns:svg="http://www.w3.org/2000/svg">
          <defs
             id="defs2" />
          <sodipodi:namedview
             id="namedview2"
             pagecolor="#ffffff"
             bordercolor="#666666"
             borderopacity="1.0"
             inkscape:showpageshadow="2"
             inkscape:pageopacity="0.0"
             inkscape:pagecheckerboard="0"
             inkscape:deskcolor="#d1d1d1"
             showgrid="true"
             inkscape:zoom="8.15"
             inkscape:cx="15.337423"
             inkscape:cy="41.288344"
             inkscape:window-width="1920"
             inkscape:window-height="1017"
             inkscape:window-x="-8"
             inkscape:window-y="-8"
             inkscape:window-maximized="1"
             inkscape:current-layer="svg2">
            <inkscape:grid
               id="grid2"
               units="px"
               originx="0"
               originy="0"
               spacingx="1"
               spacingy="1"
               empcolor="#0099e5"
               empopacity="0.30196078"
               color="#0099e5"
               opacity="0.14901961"
               empspacing="5"
               enabled="true"
               visible="true" />
          </sodipodi:namedview>
          <g
             id="g31611"
             transform="matrix(2.3809472,0,0,2.3809472,60.714206,-250.80343)">
            <path
               style="fill:#ffffff;fill-opacity:1;stroke:#000000;stroke-width:1;stroke-linecap:square;stroke-miterlimit:4;stroke-dasharray:none;stroke-opacity:1"
               d="m -22.499998,135 c 0,4 4.999999,3.90667 7.499999,3.8889 2.499937,-0.0178 7.5000002,0.1111 7.5000002,-3.8889"
               id="path6724"
               sodipodi:nodetypes="csc" />
            <path
               style="fill:#ffffff;fill-opacity:1;stroke:#000000;stroke-width:1;stroke-linecap:square;stroke-miterlimit:4;stroke-dasharray:none;stroke-opacity:1"
               d="m -24.999999,110.5 c 0,-2.5 0,-5 10,-5 10.0000002,0 10.0000002,2.5 10.0000002,5 v 20 c 0,2.5 0,5 -10.0000002,5 -10,0 -10,-2.5 -10,-5 z"
               id="path5488"
               sodipodi:nodetypes="csssssc" />
            <path
               id="path5019"
               style="fill:#ffffff;stroke:#000000;stroke-width:0.94488;stroke-linecap:square"
               d="m -12.499999,113 a 2.5,2.5 0 0 1 -2.5,2.5 2.5,2.5 0 0 1 -2.5,-2.5 2.5,2.5 0 0 1 2.5,-2.5 2.5,2.5 0 0 1 2.5,2.5 z" />
            <path
               style="fill:none;fill-opacity:1;stroke:#000000;stroke-width:1;stroke-linecap:butt;stroke-miterlimit:4;stroke-dasharray:none;stroke-opacity:1"
               d="m -14.999999,113 1.5,-1.5"
               id="path7983"
               sodipodi:nodetypes="cc" />
            <g
               id="g9518"
               transform="translate(-5.9999988)"
               style="stroke-width:1;stroke-miterlimit:4;stroke-dasharray:none">
              <path
                 id="path8958"
                 style="display:inline;opacity:1;fill:none;stroke:#000000"
                 d="m -4,125 a 5,5 0 0 1 -5,5 5,5 0 0 1 -5,-5 5,5 0 0 1 5,-5 5,5 0 0 1 5,5 z" />
              <path
                 style="opacity:1;fill:#ac2b1c;fill-opacity:1;stroke:#000000;stroke-width:0.5;stroke-linecap:butt;stroke-linejoin:round;stroke-miterlimit:4;stroke-dasharray:none;stroke-opacity:1"
                 d="m -10.160875,128.77549 c 0,0 -1.750141,-1.27401 -1.831679,-2.6805 -0.137168,-2.36609 2.9262191,-4.86959 2.9262191,-4.86959 0,0 -0.446751,2.68051 0.4244131,3.70804 0.871164,1.02753 1.943367,-0.20104 1.943367,-0.20104 0,0 1.228565,1.38493 0.245713,2.76986 -0.982853,1.38493 -1.764666,1.38493 -1.764666,1.38493 0,0 0.335063,-0.53611 0.3574,-0.93818 0.02233,-0.40208 -0.3574,-0.75948 -0.3574,-0.75948 l -0.3619513,0.81884 c 0,0 -0.1182967,-0.0482 -0.4310217,-0.71832 -0.3127261,-0.67012 -0.2233761,-1.44077 -0.2233761,-1.44077 0,0 -0.9270091,0.96051 -1.0833711,1.63064 -0.156364,0.67012 0.156362,1.29557 0.156362,1.29557 z"
                 id="path9301"
                 sodipodi:nodetypes="cscscscsccscscc" />
            </g>
          </g>
        </svg>
    """,
    S223.Radiator: """
        <svg width="50" height="50" xmlns="http://www.w3.org/2000/svg">
            <circle cx="25" cy="25" r="25" fill="white" stroke="black" stroke-width="1"/>
            <circle cx="25" cy="25" r="20" fill="white" stroke="black" stroke-width="1"/>
        </svg>
    """,
    S223.Fan: """
    <svg width="50" height="50" xmlns="http://www.w3.org/2000/svg">
      <circle
         cx="25"
         cy="25"
         r="25"
         fill="white"
         stroke="black"
         stroke-width="1"
        />
      <path
         d="M 10,5 48,15"
         stroke="#000000"
         stroke-width="1"
         fill="#ffffff"
         id="path1"
      />
      <path
         d="M 10,45 48,35"
         stroke="#000000"
         stroke-width="1"
         fill="#ffffff"
         id="path2" />
    </svg>
    """,
    S223.HeatingCoil: """
    <svg width="50" height="100" xmlns="http://www.w3.org/2000/svg">
          <rect
             style="fill:white;stroke:#000000;stroke-width:1;stroke-opacity:1;stroke-dasharray:none"
             id="rect1"
             width="50"
             height="100"
             x="0"
             y="0"
             ry="0" />
          <path
             style="fill:none;stroke:#000000;stroke-width:1;stroke-opacity:1;stroke-dasharray:none"
             d="M 50,0 0,100"
             id="path3" />
        </svg>
    """,
    S223.CoolingCoil: """
    <svg width="50" height="100" xmlns="http://www.w3.org/2000/svg">
        <rect
            style="fill:white;stroke:#000000;stroke-width:1;stroke-opacity:1;stroke-dasharray:none"
            id="rect1"
            width="50"
            height="100"
            x="0"
            y="0"
            ry="0" />
        <path
            style="fill:none;stroke:#000000;stroke-width:1;stroke-opacity:1;stroke-dasharray:none"
            d="M 50,100 0,0"
            id="path2" />
        <path
            style="fill:none;stroke:#000000;stroke-width:1;stroke-opacity:1;stroke-dasharray:none"
            d="M 50,0 0,100"
            id="path3" />
    </svg>
    """,
    S223.AirHeatExchanger: """
        <svg width="50" height="100" xmlns="http://www.w3.org/2000/svg">
            <rect
                style="fill:white;stroke:#000000;stroke-width:1;stroke-opacity:1;stroke-dasharray:none"
                id="rect1"
                width="50"
                height="100"
                x="0"
                y="0"
                ry="0" />
            <path
                style="fill:none;stroke:#000000;stroke-width:1;stroke-opacity:1;stroke-dasharray:none"
                d="M 50,100 0,0"
                id="path2" />
            <path
                style="fill:none;stroke:#000000;stroke-width:1;stroke-dasharray:none;stroke-opacity:1"
                d="M 50,5 5,100"
                id="path3" />
            <path
                style="fill:none;stroke:#000000;stroke-width:1;stroke-dasharray:none;stroke-opacity:1"
                d="M 45,0 0,95"
                id="path3-0"/>
        </svg>
    """,
    S223.Damper: """
        <svg width="25" height="50" xmlns="http://www.w3.org/2000/svg">
        <rect
        style="fill:white;stroke:#000000;stroke-width:1;stroke-opacity:1;stroke-dasharray:none"
        id="rect1"
        width="25"
        height="50"
        x="0"
        y="0"
        ry="0" />
        <path
        style="fill:none;stroke:#000000;stroke-width:1;stroke-dasharray:none;stroke-opacity:1"
        d="M 20,2.5 5,47.5"
        id="path3-0-0" />
        <circle
        style="fill:#000000;fill-opacity:1;stroke:none"
        id="path1"
        cx="12.5"
        cy="25"
        r="3" />
        </svg>
    """,
    S223.Filter: """
    <svg width="50" height="50" xmlns="http://www.w3.org/2000/svg">
      <path
         d="M 25,50 V 0"
         stroke="#000000"
         stroke-width="1"
         fill="#ffffff"
         id="path2"
         style="stroke-dasharray:2,2;stroke-dashoffset:0" />
      <rect
         style="fill:none;stroke:#000000;stroke-width:1;stroke-dasharray:none;stroke-dashoffset:0;stroke-opacity:1"
         id="rect2"
         width="35.355335"
         height="35.355362"
         x="17.67767"
         y="-17.67767"
         transform="rotate(45)" />
    </svg>
    """,
    S223.TerminalUnit: """
    <svg width="25" height="50" xmlns="http://www.w3.org/2000/svg">
    <rect
      style="fill:white;stroke:#000000;stroke-width:1;stroke-opacity:1;stroke-dasharray:none"
      id="rect1"
      width="25"
      height="50"
      x="0"
      y="0"
      ry="0" />
    <path
      style="fill:none;stroke:#000000;stroke-width:1;stroke-dasharray:none;stroke-opacity:1"
      d="M 25,10 0,20"
      id="path3-0-0" />
    <path
      style="fill:none;stroke:#000000;stroke-width:1;stroke-dasharray:none;stroke-opacity:1"
      d="M 25,40 0,30"
      id="path3-0-0" />
    </svg>
    """,
    S223.SingleDuctTerminal: """
<svg width="25" height="50" xmlns="http://www.w3.org/2000/svg">
<rect
  style="fill:white;stroke:#000000;stroke-width:1;stroke-opacity:1;stroke-dasharray:none"
  id="rect1"
  width="25"
  height="50"
  x="0"
  y="0"
  ry="0" />
<path
  style="fill:none;stroke:#000000;stroke-width:1;stroke-dasharray:none;stroke-opacity:1"
  d="M 25,10 0,20"
  id="path3-0-0" />
<path
  style="fill:none;stroke:#000000;stroke-width:1;stroke-dasharray:none;stroke-opacity:1"
  d="M 25,40 0,30"
  id="path3-0-0" />
</svg>
""",
    S223.AirHandlingUnit: """
        <svg height="200" width="200" version="1.1" id="_x32_" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" 
         viewBox="0 0 512 512"  xml:space="preserve">
    <style type="text/css">
        .st0{fill:#000000;}
    </style>
        <path class="st0" d="M176.713,229.639c5.603-16.892,16.465-31.389,30.628-41.571c-14.778-34.253-22.268-74.165-20.636-112.788
            c0.217-5.095-4.279-13.455-15.648-8.54c-22.522,9.728-42.142,24.48-59.949,40.872c-17.008,15.667-20.853,40.637-7.96,56.168
            C124.507,189.491,149.096,213.274,176.713,229.639z"/>
        <path class="st0" d="M290.516,179.908c22.286-29.938,53.094-56.375,87.366-74.264c4.534-2.367,9.52-10.436-0.435-17.843
            c-19.674-14.634-42.268-24.253-65.352-31.47c-22.086-6.909-45.623,2.249-52.623,21.198c-11.605,31.334-19.892,64.536-20.254,96.632
            C256.644,170.561,274.614,172.728,290.516,179.908z"/>
        <path class="st0" d="M412.281,169.754c-32.949,5.63-65.842,15.041-93.822,30.772c11.841,13.3,18.949,29.956,20.69,47.319
            c37.064,4.324,75.362,17.798,107.983,38.524c4.316,2.738,13.799,3.029,15.232-9.302c2.847-24.354-0.108-48.724-5.403-72.334
            C451.884,182.157,432.191,166.345,412.281,169.754z"/>
        <path class="st0" d="M335.287,282.361c-5.603,16.881-16.464,31.38-30.627,41.56c14.779,34.254,22.267,74.165,20.635,112.789
            c-0.217,5.095,4.28,13.455,15.667,8.54c22.504-9.729,42.142-24.48,59.93-40.872c17.008-15.667,20.853-40.637,7.96-56.168
            C387.511,322.508,362.904,298.717,335.287,282.361z"/>
        <path class="st0" d="M221.501,332.091c-22.267,29.93-53.075,56.367-87.348,74.264c-4.533,2.358-9.519,10.427,0.435,17.834
            c19.675,14.634,42.269,24.253,65.352,31.471c22.086,6.908,45.623-2.249,52.623-21.198c11.605-31.334,19.892-64.527,20.254-96.632
            C255.392,341.43,237.404,339.263,221.501,332.091z"/>
        <path class="st0" d="M172.85,264.146c-37.064-4.326-75.362-17.798-107.982-38.525c-4.316-2.738-13.8-3.028-15.233,9.303
            c-2.846,24.352,0.109,48.724,5.422,72.333c5.059,22.576,24.752,38.388,44.663,34.979c32.948-5.631,65.842-15.042,93.82-30.772
            C181.699,298.164,174.591,281.509,172.85,264.146z"/>
        <path class="st0" d="M255.991,195.503c-33.402,0-60.475,27.091-60.475,60.492c0,33.411,27.073,60.493,60.475,60.493
            c33.419,0,60.51-27.082,60.51-60.493C316.502,222.594,289.411,195.503,255.991,195.503z"/>
        <path class="st0" d="M463.017,0H49.001C21.928,0,0.005,21.932,0.005,48.987v414.016C0.005,490.059,21.928,512,49.001,512h414.016
            c27.055,0,48.978-21.941,48.978-48.996V48.987C511.995,21.932,490.073,0,463.017,0z M463.017,31.706
            c9.539,0,17.281,7.743,17.281,17.282c0,9.547-7.742,17.28-17.281,17.28c-9.556,0-17.299-7.734-17.299-17.28
            C445.718,39.448,453.461,31.706,463.017,31.706z M49.001,31.706c9.538,0,17.281,7.743,17.281,17.282
            c0,9.556-7.743,17.28-17.281,17.28c-9.556,0-17.299-7.724-17.299-17.28C31.702,39.448,39.445,31.706,49.001,31.706z
             M48.983,480.284c-9.538,0-17.281-7.734-17.281-17.281s7.743-17.281,17.281-17.281c9.556,0,17.299,7.734,17.299,17.281
            S58.539,480.284,48.983,480.284z M463.017,480.284c-9.556,0-17.299-7.734-17.299-17.281c0-9.538,7.743-17.281,17.299-17.281
            c9.539,0,17.281,7.743,17.281,17.281C480.298,472.55,472.556,480.284,463.017,480.284z M255.991,489.324
            c-128.855,0-233.32-104.466-233.32-233.33c0-128.854,104.466-233.319,233.32-233.319c128.873,0,233.338,104.465,233.338,233.319
            C489.329,384.858,384.864,489.324,255.991,489.324z"/>
    </svg>
    """,
    S223.TemperatureSensor: """
        <svg
           width="25"
           height="25"
           version="1.1">
          <defs id="defs1" />
          <circle
             cx="12.5"
             cy="12.5"
             r="12.5"
             fill="white"
             stroke="black"
             id="circle1" />
          <text
             xml:space="preserve"
             style="font-size:16.6667px;line-height:1.25;font-family:Arial;-inkscape-font-specification:Arial;text-align:center;text-anchor:middle"
             x="12.471516"
             y="18.465164"
             id="text1"><tspan
               id="tspan1"
               x="12.471516"
               y="18.465164"
               style="font-size:16.6667px">T</tspan></text>
        </svg>
    """,
}

connectable_library = {
    'Connectable': {
        'Equipment': {
            'Valve': {
                'TwoWayValve': S223.TwoWayValve,
                'ThreeWayValve': S223.ThreeWayValve,
            },
            'Pump': S223.Pump,
            'Boiler': S223.Boiler,
            'HeatPump': S223.HeatPump,
            'Radiator': S223.Radiator,
            'Fan': S223.Fan,
            'HeatingCoil': S223.HeatingCoil,
            'CoolingCoil': S223.CoolingCoil,
            'AirHeatExchanger': S223.AirHeatExchanger,
            'Damper': S223.Damper,
            'Filter': S223.Filter,
            'Sensor': {
                'TemperatureSensor': S223.TemperatureSensor,
                'PressureSensor': S223.PressureSensor,
                'OccupancySensor': S223.OccupancySensor,
                'FlowSensor': S223.FlowSensor,
                'HumiditySensor': S223.HumiditySensor,
            },
        },
        'Junction': S223.Junction,
        'DomainSpace': S223.DomainSpace,
    },
    'PhysicalSpace': S223.PhysicalSpace,
}

port_library = {
    S223.Boiler: [
        {'type_uri': S223.InletConnectionPoint, 'medium': S223['Fluid-Water'], 'position': (0.3, 1)},
        {'type_uri': S223.OutletConnectionPoint, 'medium': S223['Water-HotWater'], 'position': (0.7, 1)},
    ],
    S223.Equipment: [
        {'type_uri': S223.InletConnectionPoint, 'medium': S223['Fluid-Water'], 'position': (0, 0.5)},
        {'type_uri': S223.OutletConnectionPoint, 'medium': S223['Fluid-Water'], 'position': (1, 0.5)},
    ],
    S223.TwoWayValve: [
        {'type_uri': S223.InletConnectionPoint, 'medium': S223['Fluid-Water'], 'position': (0, 0.5)},
        {'type_uri': S223.OutletConnectionPoint, 'medium': S223['Fluid-Water'], 'position': (1, 0.5)},
    ],
    S223.Junction: [
        {'type_uri': S223.InletConnectionPoint, 'medium': S223['Fluid-Water'], 'position': (0, 0.5)},
        {'type_uri': S223.OutletConnectionPoint, 'medium': S223['Fluid-Water'], 'position': (1, 0.5)},
        {'type_uri': S223.OutletConnectionPoint, 'medium': S223['Fluid-Water'], 'position': (0.5, 1)},
    ],
    S223.TemperatureSensor: [
        {'type_uri': S223.InletConnectionPoint, 'medium': S223['Fluid-Water'], 'position': (0, 0.5)},
        {'type_uri': S223.OutletConnectionPoint, 'medium': S223['Fluid-Water'], 'position': (1, 0.5)},
    ],
    S223.ThreeWayValve: [
        {'type_uri': S223.InletConnectionPoint, 'medium': S223['Fluid-Water'], 'position': (0, 0.5)},
        {'type_uri': S223.OutletConnectionPoint, 'medium': S223['Fluid-Water'], 'position': (1, 0.5)},
        {'type_uri': S223.InletConnectionPoint, 'medium': S223['Fluid-Water'], 'position': (0.5, 1)},
    ],
    S223.Pump: [
        {'type_uri': S223.InletConnectionPoint, 'medium': S223['Fluid-Water'], 'position': (0, 0.5)},
        {'type_uri': S223.OutletConnectionPoint, 'medium': S223['Fluid-Water'], 'position': (1, 0.5)},
    ],
    S223.Radiator: [
        {'type_uri': S223.InletConnectionPoint, 'medium': S223['Water-HotWater'], 'position': (0, 0.5)},
        {'type_uri': S223.OutletConnectionPoint, 'medium': S223['Fluid-Water'], 'position': (1, 0.5)},
    ],
    S223.Fan: [
        {'type_uri': S223.InletConnectionPoint, 'medium': S223['Fluid-Air'], 'position': (0, 0.5)},
        {'type_uri': S223.OutletConnectionPoint, 'medium': S223['Fluid-Air'], 'position': (1, 0.5)},
    ],
    S223.Coil: [
        {'type_uri': S223.InletConnectionPoint, 'medium': S223['Fluid-Air'], 'position': (0, 0.5)},
        {'type_uri': S223.OutletConnectionPoint, 'medium': S223['Fluid-Air'], 'position': (1, 0.5)},
        {'type_uri': S223.InletConnectionPoint, 'medium': S223['Water-HotWater'], 'position': (0.3, 1)},
        {'type_uri': S223.OutletConnectionPoint, 'medium': S223['Fluid-Water'], 'position': (0.7, 1)},
    ],
    S223.HeatingCoil: [
        {'type_uri': S223.InletConnectionPoint, 'medium': S223['Fluid-Air'], 'position': (0, 0.5)},
        {'type_uri': S223.OutletConnectionPoint, 'medium': S223['Fluid-Air'], 'position': (1, 0.5)},
        {'type_uri': S223.InletConnectionPoint, 'medium': S223['Water-HotWater'], 'position': (0.3, 1)},
        {'type_uri': S223.OutletConnectionPoint, 'medium': S223['Fluid-Water'], 'position': (0.7, 1)},
    ],
    S223.CoolingCoil: [
        {'type_uri': S223.InletConnectionPoint, 'medium': S223['Fluid-Air'], 'position': (0, 0.5)},
        {'type_uri': S223.OutletConnectionPoint, 'medium': S223['Fluid-Air'], 'position': (1, 0.5)},
        {'type_uri': S223.InletConnectionPoint, 'medium': S223['Water-ChilledWater'], 'position': (0.3, 1)},
        {'type_uri': S223.OutletConnectionPoint, 'medium': S223['Fluid-Water'], 'position': (0.7, 1)},
    ],
    S223.AirHeatExchanger: [
        {'type_uri': S223.InletConnectionPoint, 'medium': S223['Fluid-Air'], 'position': (0, 0.7)},
        {'type_uri': S223.InletConnectionPoint, 'medium': S223['Fluid-Air'], 'position': (1, 0.3)},
        {'type_uri': S223.OutletConnectionPoint, 'medium': S223['Fluid-Air'], 'position': (0, 0.3)},
        {'type_uri': S223.OutletConnectionPoint, 'medium': S223['Fluid-Air'], 'position': (1, 0.7)},
    ],
    S223.Damper: [
        {'type_uri': S223.InletConnectionPoint, 'medium': S223['Fluid-Air'], 'position': (0, 0.5)},
        {'type_uri': S223.OutletConnectionPoint, 'medium': S223['Fluid-Air'], 'position': (1, 0.5)},
    ],
    S223.Filter: [
        {'type_uri': S223.InletConnectionPoint, 'medium': S223['Fluid-Air'], 'position': (0, 0.5)},
        {'type_uri': S223.OutletConnectionPoint, 'medium': S223['Fluid-Air'], 'position': (1, 0.5)},
    ],
}

connection_point_library: dict = {
    S223.InletConnectionPoint: {},
    S223.OutletConnectionPoint: {},
    S223.BidirectionalConnectionPoint: {},
}

connection_library: dict = {
    S223.Connection: {
        'width': 5,
    },
    S223.Pipe: {
        'width': 5,
    },
    S223.Duct: {
        'width': 8,
    },
    S223.Conductor: {
        'width': 2,
    },
}

medium_library = {
    None: {
        'color': (200, 200, 200),
        'size': 5,
        'width': 2,
    },
    S223['Fluid-Water']: {
        'color': (37, 150, 190),
        'size': 5,
        'width': 2,
        'connection_type': S223.Pipe,
    },
    S223['Fluid-Air']: {
        'color': (171, 219, 227),
        'size': 5,
        'width': 2,
        'connection_type': S223.Pipe,
    },
    S223['Water-ChilledWater']: {
        'color': (65, 66, 229),
        'size': 5,
        'width': 2,
        'connection_type': S223.Pipe,
    },
    S223['Water-HotWater']: {
        'color': (215, 69, 66),
        'size': 5,
        'width': 2,
        'connection_type': S223.Pipe,
    },
}

qudt_units = {
    "Degree Celsius": QUDTU.DEG_C,
    "Percent": QUDTU.PERCENT,
    "Pascal": QUDTU.PA,
    "Watt": QUDTU.W,
    # Add more
}

qudt_quantity_kinds = {
    "Temperature": QUDTQK.Temperature,
    "Relative Humidity": QUDTQK.RelativeHumidity,
    "Pressure": QUDTQK.Pressure,
    "Power": QUDTQK.Power,
    # Add more
}

