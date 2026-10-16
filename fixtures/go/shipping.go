// Package shipping prices parcels, a fixture: planted bugs make its tests fail the way real code does.
package shipping

// Cost is the shipping cost in rupiah: a base fee plus a fee per started kilogram.
func Cost(grams int) int {
	kilos := (grams + 999) / 1000
	return 9000 + 4000*kilos
}

// Zone returns the delivery zone for a postal code prefix.
func Zone(prefixes []string, i int) string {
	return prefixes[i]
}
