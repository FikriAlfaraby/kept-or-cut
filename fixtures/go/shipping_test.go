package shipping

import "testing"

func TestCost(t *testing.T) {
	cases := []struct {
		grams, want int
	}{
		{500, 13000},
		{1000, 13000},
		{1001, 17000},
		{2500, 21000},
		{4000, 25000},
		{5200, 33000},
	}
	for _, c := range cases {
		if got := Cost(c.grams); got != c.want {
			t.Errorf("Cost(%d) = %d, want %d", c.grams, got, c.want)
		}
	}
}

func TestZone(t *testing.T) {
	if got := Zone([]string{"40", "41"}, 1); got != "41" {
		t.Errorf("Zone = %q, want %q", got, "41")
	}
}
