import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { ArrowLeft, Plus } from 'lucide-react'
import { Card, CardHeader } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { Button } from '../components/ui/Button'
import { PhotoCapture } from '../components/ui/PhotoCapture'
import { getPerson, createPerson, updatePerson, uploadPhotoBase64, getPhotoUrl } from '../api/people'
import { quickPrefix } from '../api/auth'
import { listCompanies, createCompany } from '../api/companies'

const schema = z.object({
  first_name: z.string().min(1, 'Required').max(100, 'Too long'),
  last_name: z.string().min(1, 'Required').max(100, 'Too long'),
  email: z.string().email('Valid email required').max(255, 'Too long'),
  phone: z.string().max(30).optional(),
  person_type: z.enum(['employee', 'contractor']),
  job_title: z.string().min(1, 'Required').max(200, 'Too long'),
  department: z.string().min(1, 'Required').max(100, 'Too long'),
  floor: z.string().max(50).optional(),
  notes: z.string().max(1000).optional(),
  id_letter: z.string()
    .max(5, 'Max 5 letters')
    .regex(/^[A-Za-z]*$/, 'Letters only')
    .optional(),
  company_id: z.string().min(1, 'Select a company'),
  contract_start: z.string().min(1, 'Contract start date required'),
  status: z.enum(['active', 'inactive', 'suspended', 'terminated']).optional(),
})

type FormValues = z.infer<typeof schema>

export function PersonFormPage() {
  const { id } = useParams<{ id: string }>()
  const isEdit = !!id
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [newCompanyName, setNewCompanyName] = useState('')
  const [addingCompany, setAddingCompany] = useState(false)
  const [companyError, setCompanyError] = useState('')

  const pendingBase64 = useRef<string | null>(null)

  const { data: existing } = useQuery({
    queryKey: ['person', id],
    queryFn: () => getPerson(id!),
    enabled: isEdit,
  })

  const { data: companies = [], refetch: refetchCompanies } = useQuery({
    queryKey: ['companies'],
    queryFn: listCompanies,
  })

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      person_type: 'employee',
      status: 'active',
      contract_start: new Date().toISOString().split('T')[0],
    },
  })

  const personType = form.watch('person_type')

  // Auto-select main company for employees
  useEffect(() => {
    if (personType === 'employee' && companies.length > 0) {
      const main = companies.find(c => c.is_main_company)
      if (main) form.setValue('company_id', main.id)
    } else if (personType === 'contractor') {
      // Clear company selection when switching to contractor so user must pick
      const current = form.getValues('company_id')
      const main = companies.find(c => c.is_main_company)
      if (current === main?.id) form.setValue('company_id', '')
    }
  }, [personType, companies, form])

  useEffect(() => {
    if (existing) {
      form.reset({
        first_name: existing.first_name,
        last_name: existing.last_name,
        email: existing.email,
        phone: existing.phone ?? '',
        person_type: existing.person_type,
        job_title: existing.job_title,
        department: existing.department,
        floor: existing.floor ?? '',
        notes: '',
        id_letter: '',
        company_id: existing.company_id,
        contract_start: existing.current_contract?.start_date
          ? String(existing.current_contract.start_date)
          : new Date().toISOString().split('T')[0],
        status: existing.status,
      })
    }
  }, [existing, form])

  async function uploadPendingPhoto(personId: string) {
    if (pendingBase64.current) {
      await uploadPhotoBase64(personId, pendingBase64.current)
    }
  }

  const mutation = useMutation({
    mutationFn: async (data: FormValues) => {
      const { id_letter, ...rest } = data
      let person
      if (isEdit) {
        person = await updatePerson(id!, rest)
      } else {
        if (!id_letter) throw new Error('id_letter required')
        const { id: prefix_id } = await quickPrefix(id_letter.toUpperCase(), data.person_type)
        person = await createPerson({ ...rest, prefix_id })
      }
      await uploadPendingPhoto(person.id).catch(() => {})
      return person
    },
    onSuccess: (p) => {
      qc.invalidateQueries({ queryKey: ['people'] })
      qc.invalidateQueries({ queryKey: ['person', id] })
      navigate(`/people/${p.id}`)
    },
  })

  async function handleAddCompany() {
    if (!newCompanyName.trim()) return
    setCompanyError('')
    try {
      const c = await createCompany(newCompanyName.trim())
      await refetchCompanies()
      form.setValue('company_id', c.id)
      setNewCompanyName('')
      setAddingCompany(false)
    } catch {
      setCompanyError('Failed to create company.')
    }
  }

  const onSubmit = (data: FormValues) => {
    if (!isEdit && !data.id_letter) {
      form.setError('id_letter', { message: 'Enter a letter (A–Z)' })
      return
    }
    mutation.mutate(data)
  }
  const err = mutation.error as { response?: { data?: { detail?: string } } } | null

  const contractorCompanies = companies.filter(c => !c.is_main_company)
  const mainCompany = companies.find(c => c.is_main_company)

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => navigate(isEdit ? `/people/${id}` : '/people')}>
          <ArrowLeft className="h-4 w-4" /> Back
        </Button>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{isEdit ? 'Edit person' : 'Add person'}</h1>
      </div>

      {err && (
        <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
          {err.response?.data?.detail ?? 'An error occurred. Please check the form.'}
        </div>
      )}

      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">

        {/* Photo */}
        <Card>
          <CardHeader title="ID card photo" />
          <div className="flex justify-center py-2">
            <PhotoCapture
              currentUrl={isEdit && existing?.has_photo ? getPhotoUrl(id!) : undefined}
              onBase64={b64 => { pendingBase64.current = b64 }}
            />
          </div>
          <p className="text-xs text-gray-400 text-center pb-2">
            Clear, forward-facing photo. Max 5 MB. Appears on the printed ID card.
          </p>
        </Card>

        {/* Identity */}
        <Card>
          <CardHeader title="Identity" />
          <div className="grid grid-cols-2 gap-4">
            <Input label="First name" required error={form.formState.errors.first_name?.message} {...form.register('first_name')} />
            <Input label="Last name" required error={form.formState.errors.last_name?.message} {...form.register('last_name')} />
            <Input label="Email" type="email" required className="col-span-2" error={form.formState.errors.email?.message} {...form.register('email')} />
            <Input label="Phone" {...form.register('phone')} />
          </div>
        </Card>

        {/* Employment */}
        <Card>
          <CardHeader title="Employment" />
          <div className="grid grid-cols-2 gap-4">

            {/* Person type */}
            <div className="col-span-2 flex flex-col gap-1">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-200">Person type <span className="text-red-500">*</span></label>
              <div className="flex gap-4">
                {(['employee', 'contractor'] as const).map(t => (
                  <label key={t} className="flex items-center gap-2 cursor-pointer">
                    <input type="radio" value={t} {...form.register('person_type')} />
                    <span className="text-sm capitalize">{t}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Company */}
            <div className="col-span-2 flex flex-col gap-1">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-200">
                {personType === 'contractor' ? "Contractor's company" : 'Company'} <span className="text-red-500">*</span>
              </label>

              {personType === 'employee' ? (
                <div className="px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 text-sm text-gray-700 dark:text-gray-200">
                  {mainCompany?.name ?? 'Loading…'}
                </div>
              ) : (
                <div className="space-y-2">
                  <select
                    className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    {...form.register('company_id')}
                  >
                    <option value="">— Select contractor company —</option>
                    {contractorCompanies.map(c => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                  {form.formState.errors.company_id && (
                    <p className="text-xs text-red-600">{form.formState.errors.company_id.message}</p>
                  )}

                  {/* Add new contractor company inline */}
                  {!addingCompany ? (
                    <button type="button" onClick={() => setAddingCompany(true)}
                      className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800">
                      <Plus className="h-3.5 w-3.5" /> Add new company
                    </button>
                  ) : (
                    <div className="flex gap-2 items-center">
                      <input
                        type="text"
                        value={newCompanyName}
                        onChange={e => setNewCompanyName(e.target.value)}
                        placeholder="Company name"
                        className="flex-1 px-3 py-1.5 rounded-lg border border-gray-300 dark:border-gray-600 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), handleAddCompany())}
                      />
                      <Button type="button" size="sm" onClick={handleAddCompany}>Add</Button>
                      <Button type="button" size="sm" variant="secondary" onClick={() => { setAddingCompany(false); setNewCompanyName('') }}>Cancel</Button>
                    </div>
                  )}
                  {companyError && <p className="text-xs text-red-600">{companyError}</p>}
                </div>
              )}
            </div>

            {/* ID Letter */}
            {!isEdit && (
              <div className="col-span-2 flex flex-col gap-1">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-200">ID letter <span className="text-red-500">*</span></label>
                <input
                  type="text"
                  maxLength={5}
                  placeholder="e.g. A"
                  className="w-32 px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-sm font-mono uppercase focus:outline-none focus:ring-2 focus:ring-blue-500"
                  {...form.register('id_letter')}
                  onChange={e => form.setValue('id_letter', e.target.value.toUpperCase())}
                />
                {form.formState.errors.id_letter && (
                  <p className="text-xs text-red-600">{form.formState.errors.id_letter.message}</p>
                )}
                <p className="text-xs text-gray-400">
                  The ID will be this letter followed by 5 random digits, e.g. <span className="font-mono">A48213</span>.
                </p>
              </div>
            )}

            <Input label="Job title" required error={form.formState.errors.job_title?.message} {...form.register('job_title')} />
            <Input label="Department" required error={form.formState.errors.department?.message} {...form.register('department')} />
            <Input label="Floor / location" {...form.register('floor')} />
            <Input
              label="Contract start date"
              type="date"
              required
              error={form.formState.errors.contract_start?.message}
              {...form.register('contract_start')}
            />
            <Input label="Notes" className="col-span-2" {...form.register('notes')} />
          </div>
        </Card>

        {/* Status — edit only */}
        {isEdit && (
          <Card>
            <CardHeader title="Status" />
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-200">Status</label>
              <select
                className="px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 w-48"
                {...form.register('status')}
              >
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
                <option value="suspended">Suspended</option>
                <option value="terminated">Terminated</option>
              </select>
            </div>
          </Card>
        )}

        <div className="flex gap-3">
          <Button type="submit" loading={mutation.isPending}>{isEdit ? 'Save changes' : 'Create person'}</Button>
          <Button type="button" variant="secondary" onClick={() => navigate(isEdit ? `/people/${id}` : '/people')}>Cancel</Button>
        </div>
      </form>
    </div>
  )
}
