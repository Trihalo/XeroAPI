from google.cloud import firestore

db = firestore.Client.from_service_account_json(
    "service-account.json",
    project="futureyou-458212",
    database="futureyou"
)

# areaMapping (aka recruiterMapping)
areaMapping = {
    "Accounting & Finance": [
        "Neha Jain", "Kate Stephenson", "Julien Dreschel", "Chloe Crewdson",
    ],
    "Technology, Business Support & Engineering": [
        "Corin Roberts", "Ashley Duffy", "Matthew Walker", "Tamsin Clark",
    ],
    "Executive": ["Emily Wilson", "Ben Wainwright"],
    "Legal": ["Suzie Large", "Emma McGuigan"],
    "Sales, Marketing & Digital": ["Lisa Chesterman", "Natalie Gibbins"],
}

# summaryMapping is the final area allocation
summaryMapping = {
    "Accounting & Finance": areaMapping["Accounting & Finance"],
    "Legal": areaMapping["Legal"],
    "Executive": areaMapping["Executive"],
    "Sales, Marketing & Digital": areaMapping["Sales, Marketing & Digital"],
    "Technology": ["Corin Roberts"],
    "Business Support": ["Ashley Duffy", "Tamsin Clark"],
    "SC, Eng & Manufacturing": ["Matthew Walker"],
}

headcountByArea = {
    "Accounting & Finance": 5.4,
    "Legal": 2.5,
    "Executive": 2.2,
    "Sales, Marketing & Digital": 2.2,
    "Technology": 1.0,
    "Business Support": 1.8,
    "SC, Eng & Manufacturing": 1.0,
}

def seed_firestore():
    # 🚀 Seed recruiters
    for area, recruiters in summaryMapping.items():
        for name in recruiters:
            db.collection("recruiters").add({"name": name, "area": area})
    print("✅ Recruiters added.")

    # 🚀 Seed areas with headcount
    for area, headcount in headcountByArea.items():
        db.collection("areas").add({"name": area, "headcount": headcount})
    print("✅ Areas added.")

if __name__ == "__main__":
    seed_firestore()
