import React, { useState, useEffect } from 'react';

const Dashboard = () => {
    const [pendingApprovals, setPendingApprovals] = useState(0);
    const [recentReports, setRecentReports] = useState([]);

    useEffect(() => {
        fetch('/api/dashboard')
            .then(res => res.json())
            .then(data => {
                setPendingApprovals(data.pendingApprovals);
                setRecentReports(data.recentReports);
            });
    }, []);

    return (
        <div className="dashboard">
            <h1>Dashboard</h1>
            <p>Pending Approvals: {pendingApprovals}</p>
            <h3>Recent Reports</h3>
            <ul>
                {recentReports.map(report => (
                    <li key={report.id}>{report.name}</li>
                ))}
            </ul>
        </div>
    );
};

export default Dashboard;
