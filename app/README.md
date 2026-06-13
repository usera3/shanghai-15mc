# 15-Minute Shanghai App

This folder is the static web application for the Shanghai 15-minute city prototype.

It uses a Leaflet / OpenStreetMap basemap with a Canvas H3 overlay, so the map can be panned,
zoomed, clicked, filtered, and tuned by overlay opacity while keeping the 14k-cell H3 layer lightweight.
The app also exposes submission links, richer detail analysis for each selected hex, and transparent
method / limitation panels for review.

It can be deployed directly as a static site. No build command is required.
