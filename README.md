LACHICA, ALTHIEA ROSE

GILGON, ABEGAIL

MOLLERO, JENNY BAVE

SAKAYGUIDE: A WEB-BASED PUBLIC TRANSPORTATION ROUTE AND FARE INFORMATION SYSTEM FOR LOCAL COMMUTERS
BSIT Class Project Concept Paper


INTRODUCTION

Background of the Project
Public transportation is an important part of daily travel for people who need to reach schools, workplaces, markets, hospitals, government offices, and other destinations. In Kabankalan City, Negros Occidental, commuters use available public transportation such as buses, jeepneys, vans, and tricycles depending on their starting point and destination. However, commuters may find it difficult to identify which transportation route to take, where to board or get off, whether a transfer is needed, and how much the trip may cost. This can be especially challenging for passengers who are unfamiliar with a particular destination or route.


To address this concern, SakayGuide is being developed as a web-based public transportation route and fare information system focused on Kabankalan City. Similar to a digital route-planning service, the system will allow commuters to enter a starting point and a destination and view available public transportation routes. It will present relevant route details, including transportation type, stops, transfer instructions when applicable, and estimated fares. Through this information, commuters will be able to plan their trips and prepare for their transportation expenses before travelling.


The system will also include supporting features for managing transportation locations, routes, and fare information. An administrative interface will allow authorized users to maintain the records used by the route-searching function, while an activity dashboard will present recorded search activity and popular destinations. The system will focus on providing organized local transportation information and will not claim to provide live vehicle tracking or guaranteed real-time arrival information.


Statement of the Problem or Project Objectives

The main objective of this project is to develop and evaluate SakayGuide, a web-based public transportation route and fare information system that will help commuters identify available public transportation routes and estimated fares between selected locations in Kabankalan City, Negros Occidental.

Specifically, the project will aim to accomplish the following objectives:

1. Develop a route-searching feature that will allow users to enter a starting point and destination within the system's defined coverage.
2. Display available public transportation routes based on the locations selected by the user and the route records stored in the system.
3. Present route details such as transportation type, identified stops, boarding and drop-off points, and transfer instructions when applicable.
4. Calculate and display estimated transportation fares using the fare information maintained in the system.
5. Provide location and landmark information to help commuters identify relevant terminals, stops, and destinations.
6. Develop administrative functions for authorized users to add, update, and manage route, location, and fare records.
7. Provide an activity dashboard that will summarize recorded searches and popular destinations for system monitoring.
8. Evaluate the system's functionality, usability, and accuracy of displayed route and fare information through testing and feedback from intended users and project evaluators.

   
Significance of the Project

The proposed SakayGuide system is expected to provide practical benefits to the following:
- Local Commuters: The system will help commuters identify available public transportation routes, understand where to board or transfer, and check estimated fares before travelling.
- Students: The system will provide students with an accessible way to search for transportation routes to schools and other destinations within the system's coverage.
- First-Time Passengers and Visitors: The system will help users who are unfamiliar with certain locations understand possible routes, stops, and transfer points.
- Authorized Administrators: The administrative features will support the organized management and updating of transportation routes, locations, and fare information.
- Future Researchers and Students: The project may serve as a reference for future studies involving web-based transportation information and local route-planning systems.
Alignment with Institutional Research Agenda and Sustainable Development Goals
Institutional Research Agenda Alignment: The project may align with the institution's research priorities related to information technology, digital innovation, or community-oriented information systems. It will apply web technologies to organize local public transportation information and make route and fare details more accessible to commuters. The final wording of this alignment will be adjusted to match the institution's official research agenda.


Sustainable Development Goal Alignment: The project will support SDG 9 (Industry, Innovation, and Infrastructure) by using a web-based information system to organize and provide access to local transportation information. It may also contribute to SDG 11 (Sustainable Cities and Communities) by helping commuters identify available public transportation options and plan their trips using route and fare information.


SCOPE AND LIMITATIONS

System Scope and Technical Architecture
SakayGuide will focus on public transportation route and fare information within Kabankalan City, Negros Occidental, including its 32 barangays and selected regular transportation connections supported by gathered route information. The system will be intended for commuters who need to search for a route from a starting point to a destination. It will use the route, stop, location, and fare records stored in its database to present available trip information.
The system will include the following major components:
• Route Search and Trip Planning: Users will be able to enter or select a starting point and destination. The system will search its available route records and display matching transportation options.
• Route Details and Transfer Instructions: The system will present the identified transportation type, route stops, boarding and drop-off points, and transfer instructions when a trip requires more than one ride.
• Estimated Fare Information: The system will calculate and display estimated fares based on the fare records and rules maintained in the database. If a trip requires multiple rides, the system will present the applicable estimated fare information for the trip.
• Locations and Map Display: The system will organize locations across the covered barangays and display recorded locations on a map to help users identify places relevant to their trips. A current-location option may be used where supported and permitted by the user's device and browser.
• Administrative Management: Authorized administrators will be able to manage transportation-related records, including locations, terminals, transport types, routes, stops, fare information, schedules, and other supporting data used by the system.
• Activity Monitoring: The system will provide an activity dashboard that will display recorded route searches, search statistics, popular destinations, and relevant audit information.
Technology Stack
The system will use Python and the Django framework for backend processing, HTML5, CSS3, and JavaScript for the user interface, and MySQL/MariaDB as the relational database management system for storing transportation-related information. Visual Studio Code will be used as the primary development environment. The system will be developed and tested in a local web environment before any approved deployment.
Target Users
The target users will include local commuters, students, first-time passengers, and other individuals who need public transportation route and fare information within the system's defined coverage. Authorized administrators will also use the system to manage and update the transportation information stored in the database.
Limitations
The system will have the following limitations:
• Geographic Coverage: The system will focus on Kabankalan City and selected regular transportation connections supported by gathered information. It will not serve as a complete transportation directory for other cities or the entire Philippines.
• Route Availability: The system will provide route guidance based on the records stored in its database. It will not guarantee that every displayed route or vehicle will be available at the time a commuter travels.
• Fare Accuracy: Estimated fares will depend on the accuracy and updating of the fare records. Actual fares may vary according to transport type, passenger category, route conditions, and applicable fare regulations.
• Real-Time Tracking: The map and current-location option will support location identification and trip planning but will not provide live tracking of buses, jeepneys, vans, or tricycles.
• Traffic and Schedule Information: The system will not provide guaranteed real-time traffic conditions, vehicle arrival times, or live schedule updates.
• Online Payments and Notifications: The system will not include online payment processing or SMS notification services in the current development scope.
• Data Maintenance: The accuracy and usefulness of the information will depend on periodic review and updating of route, location, stop, and fare records by authorized users.


ACCOUNT SYSTEM AND ACCESS CONTROL

SakayGuide has exactly two account types, both built on Django's built-in
authentication system. The single role flag is ``User.is_staff``: a staff
account is an ADMINISTRATOR with full management permissions, every other
account is a COMMUTER. There is no separate super administrator role and no
separate super administrator dashboard. No public form exposes a role field,
so self-registration can never produce an administrator.

Administrator
• Sign in at ``/administrator/login/`` (username or e-mail address).
• Lands on the admin dashboard at ``/management/``.
• Full system control: creates, edits, activates, deactivates and deletes
  commuter accounts, creates and manages other administrator accounts, and
  assigns either role.
• Manages locations and destinations, jeepney and tricycle routes, boarding
  and drop-off points, transportation stops and terminals, transfer locations,
  fares, estimated travel times and the Google Maps coordinate registry.
• Monitors commuter route searches, reads the administrator activity log,
  opens the management reports and the system monitoring console.
• Cannot open Find My Route, the Google Maps navigation view or the live GPS
  interface.

Commuter
• Self-registers at ``/commuter/register/`` and signs in at
  ``/commuter/login/`` (username or e-mail address).
• Lands on the commuter dashboard at ``/commuter/``.
• Uses Find My Route at ``/plan/`` with the Google Maps view, the live GPS
  marker, the step-by-step travel guide, the estimated fare breakdown and the
  estimated travel time.
• Reviews their own recent searches and saved routes, edits their own
  profile, changes their own password and signs out.
• Cannot open any administration URL, account record or transportation
  record.

Role unification
Existing accounts are preserved exactly as they are. Accounts that were
created as Django superusers keep their account, their password and their
permissions, and are reported as administrators everywhere in the interface.
The Django ``is_superuser`` flag is a framework permission (it opens the
built-in Django admin site at ``/admin/``); it is never granted or revoked
through the SakayGuide interface, which only ever assigns the administrator
or the commuter role. Accounts created in the interface never receive the
Django superuser flag.

Two safety rules protect the console from locking itself out: an
administrator cannot deactivate or demote their own account, and the last
active administrator can never be deactivated or demoted.

Server-side enforcement
``apps/core/permissions.py`` holds the two guards used across the project:

* ``administrator_required`` protects every management URL and backend view.
* ``commuter_required`` protects Find My Route, the map and live GPS
  endpoints, and every commuter account page.

Unauthenticated visitors are redirected to the sign-in page of the area they
tried to reach. A signed-in user of the wrong role receives HTTP 403 with the
styled access-denied page, so hiding a navigation link is never the only
protection. CSRF protection, Django password hashing, role validation during
authentication and server-enforced role rules on the account forms keep the
two account types apart.

Creating the first administrator
    python manage.py createsuperuser

The command creates the initial highest-privilege administrator account: an
active staff account with the Django superuser flag, which the application
treats as an administrator like every other staff account. The project also
ships ``python manage.py create_admin`` for a guided bootstrap that mirrors
the account into the SakayGuide audit trail. No credentials are hard-coded,
and no administrator can be created from the public registration form.

Running the tests
    python manage.py test

The suite covers both account types, the role separation, the unified
administrator role, the protected URLs and the account forms. The SakayGuide
transit database is mirrored for the duration of a test run, so the tests
never write to the live transit tables.
