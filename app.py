# Leaflet HTML - Đã sửa lỗi màn hình xám/đen
    leaflet_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            html, body {{
                width: 100%;
                height: 100vh;
                margin: 0;
                padding: 0;
                overflow: hidden;
            }}
            #map {{
                width: 100%;
                height: 100vh;
                background: #f8f9fa; /* Thay màu đen #1a1a1a bằng màu nền sáng nhẹ */
            }}
            .custom-break-icon {{
                background-color: #EF4444;
                border: 2px solid #FFFFFF;
                border-radius: 50%;
                width: 24px !important;
                height: 24px !important;
                margin-left: -12px !important;
                margin-top: -12px !important;
                box-shadow: 0 0 10px rgba(239, 68, 68, 0.8);
                animation: pulse 1.5s infinite;
            }}
            @keyframes pulse {{
                0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }}
                70% {{ transform: scale(1.2); box-shadow: 0 0 0 12px rgba(239, 68, 68, 0); }}
                100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }}
            }}
            .leaflet-control-layers {{
                font-family: Arial, sans-serif;
                border-radius: 8px !important;
                box-shadow: 0 2px 8px rgba(0,0,0,0.3) !important;
            }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        <script>
            document.addEventListener("DOMContentLoaded", function() {{
                // 1. Tạo các Layer Tile ổn định không bị chặn CORS / SSL
                var streetMap = L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                    maxZoom: 19,
                    attribution: '&copy; OpenStreetMap contributors',
                    crossOrigin: true
                }});

                var satelliteMap = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                    maxZoom: 19,
                    attribution: 'Tiles &copy; Esri',
                    crossOrigin: true
                }});

                // 2. Khởi tạo bản đồ
                var map = L.map('map', {{
                    zoomControl: true,
                    attributionControl: false,
                    layers: [streetMap]
                }}).setView({json.dumps(map_center)}, {zoom_lvl});

                // 3. Control chuyển đổi lớp
                var baseMaps = {{
                    "🗺️ Đường phố": streetMap,
                    "🛰️ Vệ tinh": satelliteMap
                }};
                L.control.layers(baseMaps, null, {{ position: 'topright' }}).addTo(map);

                // 4. Vẽ các tuyến cáp (Polylines)
                var polylinesData = {json.dumps(polylines)};
                polylinesData.forEach(function(item) {{
                    var line = L.polyline(item.coords, {{
                        color: item.color,
                        weight: item.weight,
                        opacity: item.opacity
                    }}).addTo(map);
                    if (item.tooltip) line.bindTooltip(item.tooltip);
                }});

                // 5. Vẽ điểm KN (Markers)
                var markersData = {json.dumps(markers)};
                markersData.forEach(function(item) {{
                    var circle = L.circleMarker(item.coords, {{
                        radius: item.radius,
                        color: item.color,
                        fillColor: '#FFFFFF',
                        fillOpacity: 0.9,
                        weight: 2
                    }}).addTo(map);
                    if (item.popup) circle.bindPopup(item.popup);
                    if (item.tooltip) circle.bindTooltip(item.tooltip);
                }});

                // 6. Vẽ vị trí đứt cáp (Break Marker)
                var breakMarkerData = {json.dumps(break_marker)};
                if (breakMarkerData) {{
                    var breakIcon = L.divIcon({{ className: 'custom-break-icon' }});
                    var bMarker = L.marker(breakMarkerData.coords, {{ icon: breakIcon }}).addTo(map);
                    if (breakMarkerData.popup) bMarker.bindPopup(breakMarkerData.popup).openPopup();
                    if (breakMarkerData.tooltip) bMarker.bindTooltip(breakMarkerData.tooltip);
                }}

                // 7. Render lại kích thước bản đồ để tránh đơ/xám nền
                setTimeout(function() {{
                    map.invalidateSize();
                }}, 200);
            }});
        </script>
    </body>
    </html>
    """
