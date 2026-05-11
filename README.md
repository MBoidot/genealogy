# genealogy

## Data

First data file describes the links between family members.
It's the primary data file.

Data must be organized in a CSV file with this header

- ID is an increasing unique number for each member of the family

- Gen : the generation number (starting at 0 for the farthest ancestors).
Has a prime for non direct filiation

- ID_pere 	ID_mere 	ID_Conjoint : the respectives ID's of the father, mother and current husband/wife of the current family member/ replace with "/" if empty


- Naissance 	Lieu de naissance 	Deces : Date of birth (format d/mm/yyyy, place of birth, date of death (format dd/mm/yyyy))



```ID 	Prenom 	Nom 	Gen 	Naissance 	Lieu de naissance 	Deces	ID_pere 	ID_mere 	ID_Conjoint 	Union_ID	Role	Note```


## Generate visuals

Execute the script : ```create_radial_tree_union.py```
It will create 
- an intermediate csv file called ```family_data_roles_union.csv``` and extract the data to a json + html files. Simply click the link to the html or open it in a browser to see the family tree.

- An image file called timeline will display the birth to death timeline of the whole family

- An annual linear calendar with all birthdates