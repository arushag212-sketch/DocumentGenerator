import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { ClubPermissions } from '../types';

/** Current user's effective permissions in the active club; `null` while loading or without access. */
export function useClubPermissions(): { permissions: ClubPermissions | null; loading: boolean } {
  const { activeClub } = useAuth();
  const [permissions, setPermissions] = useState<ClubPermissions | null>(null);
  const [loading, setLoading] = useState(Boolean(activeClub));

  useEffect(() => {
    if (!activeClub) {
      setPermissions(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    api.clubs
      .getPermissions(activeClub.id)
      .catch(() => null)
      .then((p) => {
        if (!cancelled) setPermissions(p);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeClub?.id, activeClub?.my_role]);

  return { permissions, loading };
}
