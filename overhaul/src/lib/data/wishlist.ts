// Mirror of Rust WishlistItem struct (lib.rs · R2 section · #[serde(rename_all = "camelCase")])
export interface WishlistItem {
  wishlistItemId:      number;
  familyId:            string;
  jerseyId:            string | null;
  size:                string | null;
  playerName:          string | null;
  playerNumber:        number | null;
  patch:               string | null;
  version:             string | null;
  customerId:          string | null;
  expectedUsd:         number | null;
  status:              'active' | 'promoted' | 'cancelled';
  promotedToImportId:  string | null;
  createdAt:           string;
  notes:               string | null;
}

export const WISHLIST_TARGET_SIZE = 20; // D-Settings default per spec sec 4.6

export function statusLabel(status: WishlistItem['status']): string {
  switch (status) {
    case 'active':    return '● ACTIVE';
    case 'promoted':  return '● PROMOTED';
    case 'cancelled': return '● CANCELLED';
  }
}

export function isAssigned(item: WishlistItem): boolean {
  return item.customerId !== null && item.customerId !== '';
}
