import React, { useEffect, useState } from 'react';
import {
  Users,
  Search,
  Shield,
  ShieldAlert,
  UserCheck,
  UserX,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { api } from '../api/client';
import { User } from '../types';
import { useAuth } from '../context/AuthContext';

export const UsersPage: React.FC = () => {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [notification, setNotification] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const res = await api.admin.listUsers();
      setUsers(res.items || []);
    } catch (err: any) {
      setNotification({ text: err.message || 'Failed to fetch platform users.', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleToggleRole = async (targetUser: User) => {
    if (targetUser.id === currentUser?.id) {
      alert('You cannot modify your own administrator role.');
      return;
    }

    const newRole = targetUser.role === 'ADMIN' ? 'USER' : 'ADMIN';
    if (!window.confirm(`Change role of "${targetUser.email}" to ${newRole}?`)) return;

    try {
      await api.admin.updateUser(targetUser.id, { role: newRole });
      setUsers((prev) =>
        prev.map((u) => (u.id === targetUser.id ? { ...u, role: newRole as 'ADMIN' | 'USER' } : u))
      );
      setNotification({ text: `Updated ${targetUser.email} to ${newRole}.`, type: 'success' });
    } catch (err: any) {
      setNotification({ text: err.message || 'Role update failed.', type: 'error' });
    }
  };

  const handleToggleActive = async (targetUser: User) => {
    if (targetUser.id === currentUser?.id) {
      alert('You cannot deactivate your own account.');
      return;
    }

    const newStatus = !targetUser.is_active;
    const actionLabel = newStatus ? 'activate' : 'disable';
    if (!window.confirm(`Are you sure you want to ${actionLabel} "${targetUser.email}"?`)) return;

    try {
      await api.admin.updateUser(targetUser.id, { is_active: newStatus });
      setUsers((prev) =>
        prev.map((u) => (u.id === targetUser.id ? { ...u, is_active: newStatus } : u))
      );
      setNotification({ text: `Account for ${targetUser.email} ${actionLabel}d.`, type: 'success' });
    } catch (err: any) {
      setNotification({ text: err.message || 'Account status update failed.', type: 'error' });
    }
  };

  const filteredUsers = users.filter((u) =>
    u.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1400, margin: '0 auto', width: '100%' }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 20,
        }}
      >
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-primary)' }}>
            User Registry & Role-Based Access Control
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
            Manage platform user accounts, assign ADMIN or USER roles, and govern tenant data access.
          </p>
        </div>

        <button
          className="btn btn-secondary btn-sm"
          onClick={fetchUsers}
          disabled={loading}
          style={{ fontSize: 12 }}
        >
          <RefreshCw size={13} className={loading ? 'spin' : ''} />
          <span>Refresh</span>
        </button>
      </div>

      {notification && (
        <div
          style={{
            marginBottom: 16,
            padding: '10px 14px',
            borderRadius: 'var(--radius-sm)',
            backgroundColor:
              notification.type === 'success' ? 'var(--status-success-bg)' : 'var(--status-error-bg)',
            color: notification.type === 'success' ? 'var(--status-success)' : 'var(--status-error)',
            border: `1px solid ${
              notification.type === 'success' ? 'var(--status-success-border)' : 'var(--status-error-border)'
            }`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: 12.5,
          }}
        >
          <span>{notification.text}</span>
          <button
            className="btn btn-ghost btn-xs"
            onClick={() => setNotification(null)}
            style={{ color: 'inherit' }}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Search */}
      <div style={{ marginBottom: 16, maxWidth: 360, position: 'relative' }}>
        <Search
          size={14}
          style={{ position: 'absolute', left: 10, top: 10, color: 'var(--text-muted)' }}
        />
        <input
          className="input"
          placeholder="Search users by email..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          style={{ paddingLeft: 30, height: 34, fontSize: 12.5 }}
        />
      </div>

      {/* Users Table */}
      <div className="table-container">
        {loading && users.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-tertiary)' }}>
            Loading users registry...
          </div>
        ) : filteredUsers.length === 0 ? (
          <div className="empty-state" style={{ margin: 20 }}>
            <Users size={32} className="empty-state-icon" />
            <div className="empty-state-title">No users found</div>
            <div className="empty-state-text">No accounts match your search filter.</div>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Email Address</th>
                <th>Role</th>
                <th>Account Status</th>
                <th>Registered Date</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.map((u) => {
                const isSelf = u.id === currentUser?.id;
                return (
                  <tr key={u.id}>
                    <td style={{ fontWeight: 500, color: 'var(--text-primary)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <div
                          style={{
                            width: 24,
                            height: 24,
                            borderRadius: '50%',
                            backgroundColor: 'var(--bg-subtle)',
                            border: '1px solid var(--border-default)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: 10,
                            fontWeight: 600,
                          }}
                        >
                          {u.email.substring(0, 2).toUpperCase()}
                        </div>
                        <span>{u.email}</span>
                        {isSelf && (
                          <span className="badge badge-info" style={{ fontSize: 9.5, padding: '0 4px' }}>
                            You
                          </span>
                        )}
                      </div>
                    </td>
                    <td>
                      <span
                        className={`badge ${u.role === 'ADMIN' ? 'badge-info' : 'badge-neutral'}`}
                        style={{ textTransform: 'uppercase' }}
                      >
                        {u.role}
                      </span>
                    </td>
                    <td>
                      {u.is_active ? (
                        <span className="badge badge-success">
                          <CheckCircle2 size={11} />
                          <span>Active</span>
                        </span>
                      ) : (
                        <span className="badge badge-error">
                          <AlertCircle size={11} />
                          <span>Disabled</span>
                        </span>
                      )}
                    </td>
                    <td style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
                      {new Date(u.created_at).toLocaleDateString(undefined, {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                      })}
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 6 }}>
                        {!isSelf && (
                          <>
                            <button
                              className="btn btn-secondary btn-xs"
                              onClick={() => handleToggleRole(u)}
                              title={u.role === 'ADMIN' ? 'Demote to USER' : 'Promote to ADMIN'}
                            >
                              <Shield size={11} />
                              <span>{u.role === 'ADMIN' ? 'Set USER' : 'Set ADMIN'}</span>
                            </button>
                            <button
                              className={`btn btn-xs ${u.is_active ? 'btn-danger' : 'btn-secondary'}`}
                              onClick={() => handleToggleActive(u)}
                              title={u.is_active ? 'Disable user account' : 'Activate user account'}
                            >
                              {u.is_active ? <UserX size={11} /> : <UserCheck size={11} />}
                              <span>{u.is_active ? 'Disable' : 'Enable'}</span>
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
