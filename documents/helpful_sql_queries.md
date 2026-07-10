Compter combien de paires existe avec n_criteria ou plus
```sql
SELECT COUNT(*) FROM(
	SELECT * FROM person_comparisons WHERE n_criteria >= 5
) as result;
```
Trouver les paires qui a la personne de cette chiffe d'identité
```sql
	SELECT * FROM person_comparisons WHERE (person_id_a = 604 AND tree_id_a = 11 ) OR (person_id_b = 604 AND tree_id_b = 11);
```
Afficher l'information des paires qui ont n_criteria ou plus (et les noms des personnes, quels critères il y a, etc)
```sql
    SELECT 
	n1.n_full AS 'Nom',
	g1.gedcom_name AS 'Arbre A',
    g2.gedcom_name AS 'Arbre B',
    c.n_criteria AS 'Score (sur 7)',
    c.person_id_a AS 'ID A',
    c.person_id_b AS 'ID B',
    c.criteria AS 'Matching Criteria'
    FROM person_comparisons c
LEFT JOIN wt_gedcom g1 ON c.tree_id_a = g1.gedcom_id
LEFT JOIN wt_name n1 ON c.tree_id_a = n1.n_file AND c.person_id_a = n1.n_id AND n1.n_type = 'NAME'
LEFT JOIN wt_gedcom g2 ON c.tree_id_b = g2.gedcom_id
LEFT JOIN wt_name n2 ON c.tree_id_b = n2.n_file AND c.person_id_b = n2.n_id AND n2.n_type = 'NAME'
WHERE c.n_criteria >= 7
GROUP BY c.id;
```