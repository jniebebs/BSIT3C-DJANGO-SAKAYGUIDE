SAKAYGUIDE: A WEB-BASED PUBLIC TRANSPORTATION ROUTE AND
FARE INFORMATION SYSTEM FOR LOCAL COMMUTERS


SUMMITED BY:

MOLLERO, JENNY BAVE G.

GILGON, ABEGAIL P.

LACHICA, ALTHEIA ROSE 

November 2026

INTRODUCTION

Background of the Project

Public transportation is an essential component of daily travel for individuals who commute to schools, workplaces, public markets, healthcare facilities, government offices, and other destinations. In Kabankalan City, Negros Occidental, commuters rely on available public utility vehicles such as buses, jeepneys, vans, and tricycles depending on their point of origin and intended destination. However, passengers often encounter difficulties in identifying which transportation route to take, determining where to board or alight, recognizing whether a transfer is required, and estimating the corresponding travel fare. This navigational challenge is particularly pronounced for students, visitors, and first-time passengers who are unfamiliar with local transit routes.
To address this operational gap, the proposed project will focus on developing SakayGuide, a centralized web-based public transportation route and fare information system tailored for Kabankalan City. Similar to digital route-planning platforms, the web application will enable commuters to enter or select a starting point and a destination to view viable public transportation routes. The system will present detailed route records—including transportation mode, sequential stops, transfer instructions when multiple rides are needed, interactive map visualizations, and estimated fares—allowing commuters to plan their journeys and prepare for transportation expenses prior to traveling.
In addition, the system will include supporting administrative modules for maintaining transportation locations, routes, transfer connections, and fare matrices. An administrative dashboard will allow authorized staff and superusers to manage database records used by the route-searching function, while an activity monitoring module will summarize recorded search queries, popular destinations, and system audit logs. The project will focus on organizing local transportation records to improve public accessibility and will not claim to provide real-time GPS vehicle tracking or guaranteed live arrival schedules.

Statement of the Problem or Project Objectives

The main objective of this project is to design, develop, and evaluate SakayGuide, a web-based public transportation route and fare information system that will help commuters identify available public transportation routes and estimated fares between selected locations in Kabankalan City, Negros Occidental.

Specifically, the project will aim to accomplish the following technical objectives:

1. Develop a route-searching module that will allow users to enter or select a starting point and destination within the system's defined municipal coverage.
2. Display available direct and multi-leg public transportation routes based on user-selected locations and relational route records stored in the database.
3. Present comprehensive route details such as transportation type, sequential transit stops, boarding and drop-off points, estimated travel time, and step-by-step transfer instructions when applicable.
4. Calculate and display estimated transportation fares using active fare schedules, distance rates, and passenger discount categories (Regular, Student, Senior Citizen, and Person with Disability) maintained in the system.
5. Integrate location landmark details and interactive map displays (Google Maps API with Leaflet/OpenStreetMap fallback) to help commuters identify relevant terminals, stops, and destinations.
6. Establish role-based administrative management functions (Administrator/Staff and Superuser) with audit logging to securely add, update, and maintain route, location, stop, transfer, and fare records.
7. Provide an activity monitoring dashboard that will summarize recorded search history, popular origin-destination pairs, and missing route indicators for system oversight.
8. Conduct user acceptance testing (UAT) and evaluation with intended commuters and project evaluators to assess system functionality, usability, and the accuracy of displayed route and fare information.
   
Significance of the Project

The proposed SakayGuide system will provide direct practical value to the following beneficiaries:
•  Local Commuters: Will help daily travelers identify viable public transportation routes, understand where to board or transfer, and review estimated fares before traveling.
•  Students: Will provide students with an accessible digital reference to search for transportation routes and discounted fare estimates to schools and other destinations within Kabankalan City.
•  First-Time Passengers and Visitors: Will assist users who are unfamiliar with local areas in understanding available transit routes, landmarks, designated stops, and transfer points.
•  Authorized Administrators: Will support organized, auditable management and updating of transportation routes, locations, stops, and fare schedules.
•  Future Researchers and Students: Will serve as a reference framework for future studies involving web-based transportation information systems and local route-planning software.
Alignment with Institutional Research Agenda and Sustainable Development Goals
•  Institutional Research Agenda Alignment: Aligns with the institution's Information Technology and Community-Oriented Information Systems research priorities by applying full-stack web technologies and relational database modeling to organize local public transportation data and make route and fare details more accessible to commuters.
•  Sustainable Development Goal Alignment: 
o  SDG 9 (Industry, Innovation, and Infrastructure): Fosters technological innovation in local transit infrastructure by deploying a web-based platform that organizes and provides structured digital access to public transportation information.
o  SDG 11 (Sustainable Cities and Communities): Contributes to sustainable urban mobility by helping commuters identify available public transportation options and plan efficient, cost-effective daily trips.

SCOPE AND LIMITATIONS

System Scope & Technical Architecture

SakayGuide will cover public transportation route and fare information within Kabankalan City, Negros Occidental, including its 32 barangays and selected regular transportation connections supported by gathered local route records. The web application will serve commuters, students, visitors, and authorized administrators through a centralized relational database architecture, as summarized in Table 1.
Table 1. System Scope, Technical Architecture, and Target Users
Component	Description & Coverage
Core Modules	Route Search and Trip Planning Module, Route Details and Multi-Ride Transfer Instructions, Estimated Fare Calculator (Regular, Student, Senior Citizen, PWD), Interactive Map and Landmark Directory, Role-Based Administrative Management (Locations, Routes, Stops, Transfers, Fares, Users), and Activity & Search Monitoring Dashboard with Audit Logs.
Technology Stack	Web-based architecture utilizing Python and the Django web framework for backend processing, MySQL/MariaDB for relational database management, HTML5, CSS3, JavaScript, and Tabler UI for the front-end interface, and Google Maps JavaScript/Directions API (with Leaflet/OSRM fallback) for interactive mapping.
Target Users	Local Commuters, Students, First-Time Passengers/Visitors (registered and guest users), and Authorized System Administrators (Staff and Superusers) within Kabankalan City.

Limitations

•  Geographic Coverage: The system will focus on Kabankalan City, Negros Occidental, and selected regular transportation connections supported by gathered local information, and will not serve as a complete directory for other cities or the entire Philippines.
•  Route Availability and Real-Time Tracking: Route guidance will rely strictly on pre-recorded database entries; the system will not provide live GPS tracking of public utility vehicles, real-time traffic conditions, or guaranteed vehicle arrival schedules.
•  Fare Accuracy and Data Maintenance: Estimated fares will depend on active fare records maintained by authorized administrators and may vary from actual fares due to passenger categories, route conditions, or regulatory updates.
•  Online Payments and Notifications: Online payment processing, e-wallet transactions, and automated SMS gateway notifications will be excluded from the current development phase.
