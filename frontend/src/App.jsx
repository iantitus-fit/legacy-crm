import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { ThemeProvider } from './context/ThemeContext'
import { ToastProvider } from './context/ToastContext'
import { AIPanelProvider } from './context/AIPanelContext'
import AIPanel from './components/AIPanel'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import SetupPage from './pages/SetupPage'
import DashboardPage from './pages/DashboardPage'
import ContactsPage from './pages/ContactsPage'
import ContactDetailPage from './pages/ContactDetailPage'
import PipelineBoardPage from './pages/PipelineBoardPage'
import JobsPage from './pages/JobsPage'
import JobDetailPage from './pages/JobDetailPage'
import LeadsPage from './pages/LeadsPage'
import TasksPage from './pages/TasksPage'
import EstimatesPage from './pages/EstimatesPage'
import EstimateDetailPage from './pages/EstimateDetailPage'
import PipelineSettingsPage from './pages/PipelineSettingsPage'
import EmployeesPage from './pages/EmployeesPage'
import CrewsPage from './pages/CrewsPage'
import JobSchedulePage from './pages/JobSchedulePage'
import AppointmentsPage from './pages/AppointmentsPage'
import CustomerPortalPage from './pages/CustomerPortalPage'
import ChangeOrderPortalPage from './pages/ChangeOrderPortalPage'
import BookingPage from './pages/BookingPage'
import NotFoundPage from './pages/NotFoundPage'
import InvoiceListPage from './pages/InvoiceListPage'
import InvoiceDetailPage from './pages/InvoiceDetailPage'
import MaterialsPage from './pages/MaterialsPage'
import TemplatesPage from './pages/TemplatesPage'
import TemplateBuilderPage from './pages/TemplateBuilderPage'
import ImportContactsPage from './pages/ImportContactsPage'
import SmsSettingsPage from './pages/SmsSettingsPage'
import LeadSourceReportPage from './pages/LeadSourceReportPage'
import AutomationsListPage from './pages/AutomationsListPage'
import AutomationBuilderPage from './pages/AutomationBuilderPage'

export default function App() {
  return (
    <ThemeProvider>
    <AuthProvider>
      <ToastProvider>
      <AIPanelProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/setup" element={<SetupPage />} />
          <Route path="/portal/:token" element={<CustomerPortalPage />} />
          <Route path="/portal/co/:token" element={<ChangeOrderPortalPage />} />
          <Route path="/book" element={<BookingPage />} />
          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/contacts" element={<ContactsPage />} />
            <Route path="/contacts/:id" element={<ContactDetailPage />} />
            <Route path="/pipelines/:slug" element={<PipelineBoardPage />} />
            <Route path="/pipeline" element={<Navigate to="/pipelines/jobs" replace />} />
            <Route path="/jobs" element={<JobsPage />} />
            <Route path="/jobs/:id" element={<JobDetailPage />} />
            <Route path="/leads" element={<LeadsPage />} />
            <Route path="/tasks" element={<TasksPage />} />
            <Route path="/estimates" element={<EstimatesPage />} />
            <Route path="/estimates/:id" element={<EstimateDetailPage />} />
            <Route path="/invoices" element={<InvoiceListPage />} />
            <Route path="/invoices/:id" element={<InvoiceDetailPage />} />
            <Route path="/materials" element={<MaterialsPage />} />
            <Route path="/templates" element={<TemplatesPage />} />
            <Route path="/templates/:id" element={<TemplateBuilderPage />} />
            <Route path="/calendars/job-schedule" element={<JobSchedulePage />} />
            <Route path="/calendars/appointments" element={<AppointmentsPage />} />
            <Route path="/settings/import" element={<ImportContactsPage />} />
            <Route path="/settings/employees" element={<EmployeesPage />} />
            <Route path="/settings/crews" element={<CrewsPage />} />
            <Route path="/settings/pipelines" element={<PipelineSettingsPage />} />
            <Route path="/settings/sms" element={<SmsSettingsPage />} />
            <Route path="/automations" element={<AutomationsListPage />} />
            <Route path="/automations/:id" element={<AutomationBuilderPage />} />
            <Route path="/reports/lead-sources" element={<LeadSourceReportPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </BrowserRouter>
      <AIPanel />
      </AIPanelProvider>
      </ToastProvider>
    </AuthProvider>
    </ThemeProvider>
  )
}
